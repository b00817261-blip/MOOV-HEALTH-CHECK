"""Tests for the recursive group tree, invite tokens, and settings."""

import pytest

from moov_health_check.org import Org, ROOT_ID


@pytest.fixture
def org(tmp_path):
    return Org(str(tmp_path / "groups.json"), str(tmp_path / "settings.json"),
               desk_name="My desk")


def test_root_is_created_on_demand(org):
    groups = org.groups()
    assert ROOT_ID in groups
    assert groups[ROOT_ID]["team_name"] == "My desk"
    assert org.real_groups() == {}


def test_nested_groups_and_subtree(org):
    ops = org.add_group("Operations", ROOT_ID, leader="Diego")
    docs = org.add_group("Documentation", ROOT_ID)
    night = org.add_group("Night shift", ops["team_id"], leader="Wei")

    # Operations' subtree includes its child; the root's includes everything.
    assert set(org.subtree_ids(ops["team_id"])) == {ops["team_id"], night["team_id"]}
    assert set(org.subtree_ids(ROOT_ID)) == {
        ROOT_ID, ops["team_id"], docs["team_id"], night["team_id"]}
    assert org.depth(night["team_id"]) == 2
    assert [c["team_id"] for c in org.children(ops["team_id"])] == [night["team_id"]]


def test_invite_tokens_resolve_to_group_and_role(org):
    g = org.add_group("Operations", ROOT_ID)
    leader_tok = g["tokens"]["leader"]
    member_tok = g["tokens"]["member"]
    assert org.resolve_token(leader_tok) == (g["team_id"], "leader")
    assert org.resolve_token(member_tok) == (g["team_id"], "member")
    assert org.resolve_token("garbage") is None

    # Rotating a token invalidates the old one.
    new = org.rotate_token(g["team_id"], "member")
    assert org.resolve_token(member_tok) is None
    assert org.resolve_token(new) == (g["team_id"], "member")


def test_delete_group_removes_subtree(org):
    ops = org.add_group("Operations", ROOT_ID)
    night = org.add_group("Night", ops["team_id"])
    assert org.delete_group(ops["team_id"]) is True
    assert org.get(ops["team_id"]) is None
    assert org.get(night["team_id"]) is None  # child went too
    assert org.delete_group(ROOT_ID) is False  # never delete the root


def test_update_group(org):
    g = org.add_group("Ops", ROOT_ID)
    org.update_group(g["team_id"], team_name="Operations", leader="Diego",
                     allow_link=False)
    g2 = org.get(g["team_id"])
    assert g2["team_name"] == "Operations" and g2["leader"] == "Diego"
    assert g2["allow_link"] is False
    with pytest.raises(ValueError):
        org.update_group(g["team_id"], team_name="   ")


def test_channels_settings_roundtrip(org):
    assert [c["label"] for c in org.channels()] == ["Email", "Teams", "Note"]
    saved = org.save_channels(["Email", "SmartMOOV", "  ", "WhatsApp"])
    assert [c["label"] for c in saved] == ["Email", "SmartMOOV", "WhatsApp"]
    assert org.channels()[1] == {"key": "smartmoov", "label": "SmartMOOV"}
    # Empty falls back to defaults.
    assert len(org.save_channels(["", "  "])) == 3


def test_load_roster_reads_the_org_groups_shape(tmp_path):
    """The website writes {"groups": [...]} to the roster file; the CLI's
    load_roster must read it (and skip the synthetic root)."""
    from moov_health_check.ingest import load_roster
    org = Org(str(tmp_path / "teams.json"), str(tmp_path / "settings.json"))
    org.add_group("Operations", ROOT_ID, leader="Diego")
    org.update_group(ROOT_ID, leader="Head")  # forces a save incl. the root
    roster = load_roster(str(tmp_path / "teams.json"))
    assert set(roster) == {"operations"}          # root is skipped
    assert roster["operations"]["team_name"] == "Operations"
