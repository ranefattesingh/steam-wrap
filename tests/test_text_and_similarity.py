import pytest

from steam_wrap.core.config import GenreSettings, SimilaritySettings
from steam_wrap.schemas import Game
from steam_wrap.services import GenreMatcher, SimilarityService
from steam_wrap.services.text import normalize_key, same_series, series_label, title_tokens


def game(appid: int, name: str, **kw: object) -> Game:
    return Game(appid=appid, name=name, store_url=f"https://s/app/{appid}", **kw)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("Dark Souls", "Dark Souls III", True),
        ("Portal", "Portal 2", True),
        ("The Witcher 2", "The Witcher 3: Wild Hunt", True),
        ("Half-Life", "Half-Life: Alyx", True),
        ("Grand Theft Auto IV", "Grand Theft Auto V", True),
        ("Dead Space", "Dead Cells", False),
        ("The Long Dark", "The Long Drive", False),
        ("Stardew Valley", "Portal", False),
        ("Portal", "Portal", False),
    ],
)
def test_same_series(a: str, b: str, expected: bool) -> None:
    assert same_series(title_tokens(a), title_tokens(b)) is expected


def test_tokens_and_labels() -> None:
    assert title_tokens("Assassin\u2019s Creed® IV Black Flag™") == [
        "assassins",
        "creed",
        "iv",
        "black",
        "flag",
    ]
    assert normalize_key("Shoot 'Em Up") == "shootemup"
    assert (
        series_label([title_tokens("Dark Souls"), title_tokens("Dark Souls III")]) == "Dark Souls"
    )


def test_genre_matcher_aliases_and_direct_tags() -> None:
    matcher = GenreMatcher(GenreSettings(aliases={"shooting": ["Shooter", "FPS"]}))
    cs = game(1, "CS", tags=["FPS", "Action"], genres=["Action"])
    sv = game(2, "SV", tags=["Open World", "Casual"], genres=["Casual"])
    assert matcher.matches(cs, ["shooting"])
    assert not matcher.matches(sv, ["shooting"])
    assert matcher.matches(sv, ["open-world"])
    assert matcher.matches(cs, ["ACTION", "casual"])
    assert not matcher.matches(cs, ["action", "casual"], match_all=True)


def test_similarity_prefers_same_franchise() -> None:
    svc = SimilarityService(SimilaritySettings(min_score=0.05))
    black_flag = game(
        1,
        "Assassin's Creed IV Black Flag",
        franchises=["Assassin's Creed"],
        genres=["Action", "Adventure"],
        tags=["Pirates", "Open World", "Action", "Adventure"],
        publishers=["Ubisoft"],
    )
    unity = game(
        2,
        "Assassin's Creed Unity",
        franchises=["Assassin's Creed"],
        genres=["Action", "Adventure"],
        tags=["Open World", "Action", "Adventure"],
        publishers=["Ubisoft"],
    )
    other = game(3, "Some Open World Game", genres=["Action"], tags=["Open World", "Action"])
    unrelated = game(4, "Cozy Farm", genres=["Casual"], tags=["Farming Sim"])

    ranked = svc.rank(black_flag, [black_flag, unity, other, unrelated])
    assert [r.game.appid for r in ranked] == [2, 3]
    assert ranked[0].reasons[0] == "same franchise: Assassin's Creed"
    assert 0 < ranked[1].score < ranked[0].score <= 1

    # The public result is the same order, as plain list items.
    similar = svc.similar(black_flag, [black_flag, unity, other, unrelated])
    assert [(s.id, s.name) for s in similar] == [(2, unity.name), (3, other.name)]


def test_group_by_franchise_uses_title_fallback() -> None:
    svc = SimilarityService(SimilaritySettings())
    games = [
        game(1, "Portal"),
        game(2, "Portal 2"),
        game(3, "Assassin's Creed Unity", franchises=["Assassin's Creed"]),
        game(4, "Assassin's Creed Odyssey", franchises=["Assassin's Creed"]),
        game(5, "Stardew Valley"),
    ]
    groups = {g.name: [x.id for x in g.games] for g in svc.group(games, "franchise")}
    assert groups == {"Assassin's Creed": [4, 3], "Portal": [1, 2]}
