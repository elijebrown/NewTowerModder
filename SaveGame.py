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

_HERE = os.path.dirname(os.path.abspath(__file__))

# Lookup tables extracted from the game bundles (see the extract-*.sh scripts).
TRAIT_FILES = [
  os.path.join(_HERE, "news-tower-traits.tsv"),       # category, name, asset_guid
  os.path.join(_HERE, "natural-trait-guids.tsv"),     # asset_guid, name
]
JOBS_SKILLS_FILE = os.path.join(_HERE, "news-tower-jobs-skills.tsv")  # category, name, asset_guid
FACTIONS_FILE = os.path.join(_HERE, "news-tower-factions.tsv")        # name, asset_guid


def _load_traits(paths):
  """assetGUID -> (name, category) for every trait."""
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
          guid, name = cols          # natural traits: guid, name
          names.setdefault(guid, (name, "Natural"))
  return names


def _load_jobs_skills(path):
  """Return (jobNames, skillNames): assetGUID -> name for each category."""
  jobs, skills = {}, {}
  if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as handle:
      for line in handle:
        cols = line.rstrip("\n").split("\t")
        if len(cols) != 3 or cols[0] == "category":
          continue
        category, name, guid = cols
        (jobs if category == "Job" else skills)[guid] = name
  return jobs, skills


def _load_factions(path):
  """assetGUID -> faction name."""
  names = {}
  if os.path.exists(path):
    with open(path, "r", encoding="utf-8") as handle:
      for line in handle:
        cols = line.rstrip("\n").split("\t")
        if len(cols) == 2 and cols[1] != "asset_guid":
          name, guid = cols
          names[guid] = name
  return names


# traitIndex used when adding a brand-new trait of each category.
TRAIT_INDEX = {"Personality": 0, "Trainable": 1}


class SaveGame:
  def __init__(self, filePath):
    self.filePath = filePath
    # Name lookup tables.
    self.traitNames = _load_traits(TRAIT_FILES)
    self.jobNames, self.skillNames = _load_jobs_skills(JOBS_SKILLS_FILE)
    self.factionNames = _load_factions(FACTIONS_FILE)
    # Trait options for UI dropdowns: sorted [(name, guid)] per category.
    # TEMPORARY (testing): expose EVERY trait in both dropdowns so an in-game
    # test can reveal whether the game accepts a trait in the "wrong" slot.
    # To restore correct behaviour, revert these two lines to:
    #   self.personality_options = self._trait_options("Personality")
    #   self.trainable_options = self._trait_options("Trainable")
    self.personality_options = self._trait_options()
    self.trainable_options = self._trait_options()
    # Populated by ingestFile().
    self.header = b""
    self.trailer = b""
    self.data = None
    self.employees = []
    self.factions = []
    self._reputationNode = None
    self._next_id = 1
    self.ingestFile()

  def _trait_options(self, category=None):
    """Sorted [(name, guid)] traits; all traits when category is None."""
    opts = [(name, guid) for guid, (name, cat) in self.traitNames.items()
            if category is None or cat == category]
    return sorted(opts, key=lambda item: item[0].casefold())

  # ---- loading -----------------------------------------------------------

  def ingestFile(self):
    """Read the save, decompress its JSON payload, and load employees (name,
    job, traits, skill levels) and factions into memory."""
    with open(self.filePath, "rb") as handle:
      raw = handle.read()

    offset = raw.find(GZIP_MAGIC)
    if offset < 0:
      raise ValueError(f"No gzip payload found in save file: {self.filePath}")

    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    payload = decompressor.decompress(raw[offset:]) + decompressor.flush()

    self.header = raw[:offset]
    self.trailer = decompressor.unused_data
    self.data = json.loads(payload.decode("utf-8-sig"))

    self._next_id = self._max_id(self.data) + 1
    self.employees = self._extract_employees(self.data)
    self.factions = self._extract_factions(self.data)
    return self.employees

  def _extract_employees(self, root):
    employees = []
    for node in self._walk(root):
      if str(node.get("$type", "")).startswith("Employees.Employee+ComponentData"):
        employees.append(self._build_employee(node))
    return employees

  def _build_employee(self, node):
    nameHandler = self._child_by_type(node, "NameHandler")
    name = nameHandler.get("employeeName") if nameHandler else None

    jobHandler = self._child_by_type(node, "JobHandler")
    jobGUID = jobHandler.get("jobDataRef", {}).get("assetGUID") if jobHandler else None
    job = self.jobNames.get(jobGUID, jobGUID)

    traitHandler = self._child_by_type(node, "TraitHandler")
    traits = []
    if traitHandler is not None:
      for child in traitHandler.get("childrenData", {}).values():
        if not isinstance(child, dict):
          continue
        if not str(child.get("$type", "")).startswith("TraitSaveComponentData"):
          continue
        guid = child.get("dataRef", {}).get("assetGUID")
        resolvedName, category = self.traitNames.get(guid, (None, None))
        traits.append(Trait(guid, child.get("traitIndex"), resolvedName, category, node=child))

    skills = []
    skillHandler = self._child_by_type(node, "SkillHandler")
    if skillHandler is not None:
      for entry in skillHandler.get("dataSet", []):
        if not isinstance(entry, dict):
          continue
        guid = entry.get("skillData", {}).get("assetGUID")
        skills.append(Skill(guid, entry.get("skill"), entry.get("experience", 0),
                            name=self.skillNames.get(guid, guid), entry=entry))

    return Employee(name=name, job=job, jobGUID=jobGUID, traits=traits, skills=skills,
                    node=node, traitHandler=traitHandler)

  def _extract_factions(self, root):
    for node in self._walk(root):
      if "NpcReputationManager+ComponentData" in str(node.get("$type", "")):
        self._reputationNode = node
        identities = node.get("identities", [])
        reputation = node.get("reputation", [])
        factions = []
        for index, identity in enumerate(identities):
          guid = identity.get("assetGUID") if isinstance(identity, dict) else None
          level = reputation[index] if index < len(reputation) else None
          factions.append(Faction(guid, level, name=self.factionNames.get(guid)))
        return factions
    return []

  # ---- editing -----------------------------------------------------------

  def set_skill_level(self, skill, level):
    """Set a Skill's level (writes through to the JSON node)."""
    skill.set_level(level)

  def set_trait(self, employee, category, new_guid):
    """Set an employee's Personality or Trainable trait to new_guid, swapping
    the existing trait of that category or adding one if absent."""
    name = self.traitNames.get(new_guid, (None, None))[0]
    existing = employee.trait_by_category(category)
    if existing is not None:
      existing.set_guid(new_guid, name)
      return existing

    # Add a new TraitSaveComponentData child to the employee's TraitHandler.
    if employee.traitHandler is None:
      raise ValueError(f"{employee.name} has no TraitHandler to add a trait to")
    new_id = str(self._next_id)
    self._next_id += 1
    trait_node = {
      "$type": "TraitSaveComponentData, NewsTower",
      "traitIndex": TRAIT_INDEX.get(category, 0),
      "dataRef": {
        "$type": "Saving.SaveAssetReference, NewsTower",
        "assetGUID": new_guid,
      },
      "id": new_id,
      "childrenData": {
        "$type": "System.Collections.Generic.Dictionary`2[[System.String, mscorlib],[Saving.SaveComponentData, NewsTower]], mscorlib",
      },
    }
    employee.traitHandler.setdefault("childrenData", {})[new_id] = trait_node
    trait = Trait(new_guid, TRAIT_INDEX.get(category, 0), name, category, node=trait_node)
    employee.traits.append(trait)
    return trait

  def set_faction(self, key, reputation):
    """Set a faction's reputation by name or assetGUID (writes through)."""
    faction = self.get_faction(key)
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

  # ---- accessors ---------------------------------------------------------

  def get_employee(self, name):
    for employee in self.employees:
      if employee.name == name:
        return employee
    return None

  def get_employees(self):
    return self.employees

  def get_faction(self, key):
    for faction in self.factions:
      if key in (faction.assetGUID, faction.name):
        return faction
    return None

  def get_factions(self):
    return self.factions

  # ---- saving ------------------------------------------------------------

  def save(self, outputPath=None):
    """Write the (possibly edited) object graph back to a valid .nt file:
    original header (verbatim) + gzip(BOM + compact JSON) + md5(header+gzip).

    Writes to outputPath, or overwrites the loaded file when omitted."""
    if self.data is None:
      raise ValueError("No data loaded; call ingestFile() first.")
    if outputPath is None:
      outputPath = self.filePath

    text = json.dumps(self.data, separators=(",", ":"), ensure_ascii=False)
    payload = text.encode("utf-8-sig")
    compressed = gzip.compress(payload, mtime=0)

    body = self.header + compressed
    checksum = hashlib.md5(body).digest()

    with open(outputPath, "wb") as handle:
      handle.write(body + checksum)
    return outputPath

  # ---- helpers -----------------------------------------------------------

  @staticmethod
  def _child_by_type(node, typeFragment):
    for key, value in node.get("childrenData", {}).items():
      if key == "$type":
        continue
      if isinstance(value, dict) and typeFragment in str(value.get("$type", "")):
        return value
    return None

  @staticmethod
  def _walk(obj):
    stack = [obj]
    while stack:
      current = stack.pop()
      if isinstance(current, dict):
        yield current
        stack.extend(current.values())
      elif isinstance(current, list):
        stack.extend(current)

  @classmethod
  def _max_id(cls, root):
    """Largest numeric 'id' anywhere in the graph (for minting new ids)."""
    largest = 0
    for node in cls._walk(root):
      value = node.get("id")
      if isinstance(value, str) and value.isdigit():
        largest = max(largest, int(value))
    return largest
