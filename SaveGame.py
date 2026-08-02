import os
import json
import gzip
import zlib
import hashlib

from Employee import Employee, Trait, Skill
from Faction import Faction

# The .nt save format is a small text/binary header followed by a single
# gzip stream (magic 1f 8b 08) whose payload is a Newtonsoft JSON object graph.
GZIP_MAGIC = b"\x1f\x8b\x08"

# Default trait-guid lookup tables that live next to this file.
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TRAIT_FILES = [
  os.path.join(_HERE, "news-tower-traits.tsv"),
  os.path.join(_HERE, "natural-trait-guids.tsv"),
]


def _loadTraitNames(paths):
  """Build assetGUID -> (name, category) from the trait .tsv files.

  news-tower-traits.tsv has columns: category, name, asset_guid.
  natural-trait-guids.tsv has columns: asset_guid, name.
  """
  names = {}
  for path in paths:
    if not os.path.exists(path):
      continue
    with open(path, "r", encoding="utf-8") as handle:
      for line in handle:
        cols = line.rstrip("\n").split("\t")
        if len(cols) == 3 and cols[0] != "category":
          category, name, guid = cols
          names[guid] = (name, category)
        elif len(cols) == 2:
          guid, name = cols
          names.setdefault(guid, (name, None))
  return names


class SaveGame:
  def __init__(self, filePath, traitFiles=None):
    self.filePath = filePath
    self.traitFiles = traitFiles if traitFiles is not None else DEFAULT_TRAIT_FILES
    # Populated by ingestFile().
    self.header = b""        # raw bytes before the gzip stream
    self.trailer = b""       # trailing bytes after the gzip stream
    self.data = None         # parsed JSON object graph
    self.employees = []      # list of Employee
    self.factions = []       # list of Faction
    self._reputationNode = None  # NpcReputationManager node, for write-back
    self.ingestFile()

  def ingestFile(self):
    """Read the save file, decompress its JSON payload, and load employees
    (with their traits and skill levels) into self.employees."""
    with open(self.filePath, "rb") as handle:
      raw = handle.read()

    offset = raw.find(GZIP_MAGIC)
    if offset < 0:
      raise ValueError(f"No gzip payload found in save file: {self.filePath}")

    # Decompress exactly one gzip member; the file has a few trailing bytes.
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    payload = decompressor.decompress(raw[offset:]) + decompressor.flush()

    self.header = raw[:offset]
    self.trailer = decompressor.unused_data
    self.data = json.loads(payload.decode("utf-8-sig"))

    traitNames = _loadTraitNames(self.traitFiles)
    self.employees = self._extractEmployees(self.data, traitNames)
    self.factions = self._extractFactions(self.data)
    return self.employees

  def _extractFactions(self, root):
    """Read the single NpcReputationManager node into a list of Faction.

    `identities[i]` and `reputation[i]` are parallel arrays."""
    for node in self._walk(root):
      if "NpcReputationManager+ComponentData" in str(node.get("$type", "")):
        self._reputationNode = node
        identities = node.get("identities", [])
        reputation = node.get("reputation", [])
        factions = []
        for index, identity in enumerate(identities):
          guid = identity.get("assetGUID") if isinstance(identity, dict) else None
          level = reputation[index] if index < len(reputation) else None
          factions.append(Faction(assetGUID=guid, reputation=level))
        return factions
    return []

  def _extractEmployees(self, root, traitNames):
    """Walk the object graph and build an Employee for every
    Employees.Employee+ComponentData node."""
    employees = []
    for node in self._walk(root):
      if not str(node.get("$type", "")).startswith("Employees.Employee+ComponentData"):
        continue
      employees.append(self._buildEmployee(node, traitNames))
    return employees

  def _buildEmployee(self, node, traitNames):
    name = None
    nameHandler = self._childByType(node, "NameHandler")
    if nameHandler is not None:
      name = nameHandler.get("employeeName")

    traits = []
    traitHandler = self._childByType(node, "TraitHandler")
    if traitHandler is not None:
      for child in traitHandler.get("childrenData", {}).values():
        if not isinstance(child, dict):
          continue
        if not str(child.get("$type", "")).startswith("TraitSaveComponentData"):
          continue
        guid = child.get("dataRef", {}).get("assetGUID")
        resolvedName, category = traitNames.get(guid, (None, None))
        traits.append(Trait(
          assetGUID=guid,
          traitIndex=child.get("traitIndex"),
          name=resolvedName,
          category=category,
        ))

    skills = []
    skillHandler = self._childByType(node, "SkillHandler")
    if skillHandler is not None:
      for entry in skillHandler.get("dataSet", []):
        if not isinstance(entry, dict):
          continue
        skills.append(Skill(
          assetGUID=entry.get("skillData", {}).get("assetGUID"),
          level=entry.get("skill"),
          experience=entry.get("experience", 0),
        ))

    return Employee(name=name, traits=traits, skills=skills, node=node)

  @staticmethod
  def _childByType(node, typeFragment):
    """Return the first child component whose $type contains typeFragment."""
    for key, value in node.get("childrenData", {}).items():
      if key == "$type":
        continue
      if isinstance(value, dict) and typeFragment in str(value.get("$type", "")):
        return value
    return None

  @staticmethod
  def _walk(obj):
    """Yield every dict in the JSON object graph (depth-first)."""
    stack = [obj]
    while stack:
      current = stack.pop()
      if isinstance(current, dict):
        yield current
        stack.extend(current.values())
      elif isinstance(current, list):
        stack.extend(current)

  def getEmployee(self, name):
    for employee in self.employees:
      if employee.name == name:
        return employee
    return None

  def getEmployees(self):
    return self.employees

  def getFaction(self, key):
    """Look up a faction by assetGUID or resolved name."""
    for faction in self.factions:
      if key in (faction.assetGUID, faction.name):
        return faction
    return None

  def getFactions(self):
    return self.factions

  def setEmployee(self):
    return

  def setFaction(self, key, reputation):
    """Set a faction's reputation, updating both the Faction object and the
    underlying JSON node so the change is written out by save()."""
    faction = self.getFaction(key)
    if faction is None:
      raise KeyError(f"No faction matching {key!r}")
    faction.reputation = reputation
    if self._reputationNode is not None:
      identities = self._reputationNode.get("identities", [])
      for index, identity in enumerate(identities):
        if isinstance(identity, dict) and identity.get("assetGUID") == faction.assetGUID:
          self._reputationNode["reputation"][index] = reputation
          break
    return faction

  def save(self, outputPath=None):
    """Write the (possibly edited) object graph back to a valid .nt file.

    Format: original header (verbatim) + gzip(BOM + compact JSON) +
    a 16-byte md5 checksum of everything preceding it.

    Writes to outputPath, or overwrites the loaded file when omitted."""
    if self.data is None:
      raise ValueError("No data loaded; call ingestFile() first.")
    if outputPath is None:
      outputPath = self.filePath

    # Newtonsoft emits compact UTF-8 JSON prefixed with a BOM.
    text = json.dumps(self.data, separators=(",", ":"), ensure_ascii=False)
    payload = text.encode("utf-8-sig")

    # mtime=0 keeps the gzip stream deterministic across saves.
    compressed = gzip.compress(payload, mtime=0)

    body = self.header + compressed
    checksum = hashlib.md5(body).digest()

    with open(outputPath, "wb") as handle:
      handle.write(body + checksum)
    return outputPath
