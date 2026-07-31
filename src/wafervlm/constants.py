"""단일 소스: 라벨 매핑, 통제 어휘, 렌더링/경로 상수
"""
from __future__ import annotations

from pathlib import Path

# 경로
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
WM811K_PKL = Path("/home/work/sem-agent/MIR-WM811K/Python/WM811K.pkl")
MIXEDWM38_NPZ = Path("/home/work/sem-agent/MixedWM38/Wafer_Map_Datasets.npz")

# ---------------------------------------------------------------- 확정 결함 패턴 어휘 (KG 공유, 9종)
PATTERNS = (
    "Center",
    "Donut",
    "Edge-Loc",
    "Edge-Ring",
    "Loc",
    "Near-Full",
    "Scratch",
    "Random",
    "None",
)

# 데이터셋 원본 표기 → 확정 어휘 (WM811K는 none/Near-full 표기)
RAW_LABEL_MAP = {
    "Center": "Center",
    "Donut": "Donut",
    "Edge-Loc": "Edge-Loc",
    "Edge-Ring": "Edge-Ring",
    "Loc": "Loc",
    "Near-full": "Near-Full",
    "Scratch": "Scratch",
    "Random": "Random",
    "none": "None",
}

# MixedWM38 arr_1 의 multi-hot 컬럼 순서 (원 저장소 문서 기준)
MIXEDWM38_LABEL_ORDER = (
    "Center",
    "Donut",
    "Edge-Loc",
    "Edge-Ring",
    "Loc",
    "Near-Full",
    "Scratch",
    "Random",
)

# ---------------------------------------------------------------- 공간/형상 통제 어휘 (KG 측과 합의 대상)
ZONES = ("center", "mid", "edge", "full")
SHAPES = ("ring", "line", "cluster", "scatter", "arc", "blob", "none")
CLOCK_DIRECTIONS = tuple(f"{h}시" for h in range(1, 13)) + ("전방위",)
CONFIDENCES = ("high", "medium", "low")

# ---------------------------------------------------------------- 렌더링 (두 데이터셋 동일 적용 — 분포 지름길 학습 방지)
RENDER_SIZE = 448  # nearest 업스케일 목표 한 변 픽셀
# 값 0(배경)/1(정상 die)/2(불량 die) → RGB
RENDER_PALETTE = {
    0: (20, 20, 20),      # 배경: 거의 검정
    1: (70, 130, 90),     # 정상 die: 녹회색
    2: (255, 210, 60),    # 불량 die: 노랑
}

# ---------------------------------------------------------------- 기하 판정 임계값 (geometry.py / hard_pairs.py 공용)
R_INNER = 0.35   # 이 반경 이하 = center 영역
R_EDGE = 0.80    # 이 반경 이상 = edge 영역
NEAR_FULL_RATIO = 0.55       # 불량률이 이 이상이면 near-full 급
MIN_CLUSTER_SIZE = 3         # 이보다 작은 connected component 는 노이즈 취급
ANGULAR_BINS = 12            # 시계 12방위

# ---------------------------------------------------------------- 학습/추론 공통
CHAT_SYSTEM_PROMPT = (
    "당신은 반도체 웨이퍼맵(Wafer Bin Map) 결함 판독 전문가입니다. "
    "이미지에서 관측되는 사실(패턴 유형, 공간 분포, 형상)만 서술하고, "
    "공정 원인은 추정하지 않습니다. 답변은 지정된 JSON 스키마를 따릅니다."
    "한국어로만 서술하고, 반도체 전문 용어는 영어로 표기합니다." # zeroshot_probe 결과가 영문-중국어 혼용이라 추가함(26.07.06)
)
THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"
