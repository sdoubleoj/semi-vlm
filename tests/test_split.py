"""분할 규칙 검증: 내용 해시 동거(중복 누수 방지) + WM811K 유래 샘플 제외."""
import pandas as pd

from wafervlm.data.split import split_mixed38, split_wm811k, wm811k_derived_mask


def _mixed_df(n: int = 600) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append(
            {
                "id": f"mixed38_{i}",
                "source": "mixed38",
                "labels": ["Center"] if i % 2 else ["Center", "Scratch"],
                "lot": None,
                # 3개씩 같은 내용(완전중복 상황 재현)
                "map_hash": 1000 + i // 3,
            }
        )
    return pd.DataFrame(rows)


def test_duplicate_maps_colocate():
    df = split_mixed38(_mixed_df(), salt=42)
    n_splits_per_hash = df.groupby("map_hash")["split"].nunique()
    assert (n_splits_per_hash == 1).all(), "동일 내용 맵이 서로 다른 split에 존재"


def test_split_deterministic():
    df = _mixed_df()
    a = split_mixed38(df, salt=42)["split"].tolist()
    b = split_mixed38(df, salt=42)["split"].tolist()
    assert a == b


def test_split_has_all_parts():
    df = split_mixed38(_mixed_df(), salt=42)
    assert set(df["split"]) == {"train", "val", "test"}


def test_wm811k_derived_mask():
    df = pd.DataFrame(
        {
            "source": ["mixed38", "mixed38", "mixed38", "mixed38", "wm811k"],
            "labels": [
                ["Random"],          # 제외
                ["Near-Full"],       # 제외
                ["Center", "Loc"],   # 혼합 → 유지
                ["Center"],          # 다른 단독 → 유지
                ["Random"],          # WM811K 원본 → 유지
            ],
        }
    )
    assert wm811k_derived_mask(df).tolist() == [True, True, False, False, False]


def test_wm811k_lot_group_split():
    rows = []
    for lot in range(50):
        for w in range(4):
            rows.append(
                {
                    "id": f"wm811k_{lot}_{w}",
                    "source": "wm811k",
                    "labels": ["None"],
                    "lot": f"lot{lot}",
                }
            )
    df = split_wm811k(pd.DataFrame(rows), salt=42)
    assert (df.groupby("lot")["split"].nunique() == 1).all()
