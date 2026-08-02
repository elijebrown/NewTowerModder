class Trait:
  """A single trait on an employee, as stored in a TraitSaveComponentData."""

  def __init__(self, assetGUID, traitIndex=None, name=None, category=None):
    self.assetGUID = assetGUID
    self.traitIndex = traitIndex
    # Resolved from the traits .tsv; fall back to the raw GUID when unknown.
    self.name = name if name is not None else assetGUID
    self.category = category

  def __repr__(self):
    return f"Trait({self.name!r}, index={self.traitIndex})"


class Skill:
  """One skill entry from a SkillHandler dataSet. `level` is the 0-5 rating."""

  def __init__(self, assetGUID, level, experience=0):
    self.assetGUID = assetGUID
    self.level = level
    self.experience = experience

  def __repr__(self):
    return f"Skill({self.assetGUID}, level={self.level})"


class Employee:
  """An employee loaded from a save file: a name, their traits and their skills.

  `node` is kept so edits can be written back to the same JSON object graph
  when saving."""

  def __init__(self, name, traits=None, skills=None, node=None):
    self.name = name
    self.traits = traits if traits is not None else []
    self.skills = skills if skills is not None else []
    self.node = node

  def __repr__(self):
    return f"Employee({self.name!r}, {len(self.traits)} traits, {len(self.skills)} skills)"
