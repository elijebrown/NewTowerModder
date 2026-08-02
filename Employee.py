class Trait:
  """A single trait on an employee (a TraitSaveComponentData in the save).

  `node` is the underlying JSON dict so edits write straight through."""

  def __init__(self, assetGUID, traitIndex=None, name=None, category=None, node=None):
    self.assetGUID = assetGUID
    self.traitIndex = traitIndex
    self.name = name if name is not None else assetGUID
    self.category = category
    self.node = node

  def set_guid(self, assetGUID, name=None):
    self.assetGUID = assetGUID
    self.name = name if name is not None else assetGUID
    if self.node is not None:
      self.node["dataRef"]["assetGUID"] = assetGUID

  def __repr__(self):
    return f"Trait({self.name!r}, {self.category}, index={self.traitIndex})"


class Skill:
  """One skill entry from a SkillHandler dataSet. `level` is the 0-5 rating.

  `entry` is the underlying JSON dict so set_level writes straight through."""

  def __init__(self, assetGUID, level, experience=0, name=None, entry=None):
    self.assetGUID = assetGUID
    self.level = level
    self.experience = experience
    self.name = name if name is not None else assetGUID
    self.entry = entry

  def set_level(self, level):
    self.level = level
    if self.entry is not None:
      self.entry["skill"] = level

  def __repr__(self):
    return f"Skill({self.name!r}, level={self.level})"


class Employee:
  """An employee loaded from a save file: name, job, traits and skills.

  `node`/`traitHandler` are kept so edits can be written back to the save's
  JSON object graph."""

  def __init__(self, name, job=None, jobGUID=None, traits=None, skills=None,
               node=None, traitHandler=None):
    self.name = name
    self.job = job
    self.jobGUID = jobGUID
    self.traits = traits if traits is not None else []
    self.skills = skills if skills is not None else []
    self.node = node
    self.traitHandler = traitHandler

  def trait_by_category(self, category):
    for trait in self.traits:
      if trait.category == category:
        return trait
    return None

  def __repr__(self):
    return f"Employee({self.name!r}, {self.job}, {len(self.traits)} traits, {len(self.skills)} skills)"
