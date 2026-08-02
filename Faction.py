class Faction:
  """A faction and the player's reputation with it.

  In the save the factions live in NpcReputationManager as two parallel
  arrays: `identities` (asset references) and `reputation` (the levels)."""

  def __init__(self, assetGUID, reputation, name=None):
    self.assetGUID = assetGUID
    self.reputation = reputation
    # No faction-name table extracted yet; fall back to the raw GUID.
    self.name = name if name is not None else assetGUID

  def __repr__(self):
    return f"Faction({self.name!r}, reputation={self.reputation})"
