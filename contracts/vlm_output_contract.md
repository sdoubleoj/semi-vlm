# VLM 출력 인터페이스 계약 (v1)

**대상**: "웨이퍼맵 결함 판독 및 근본 원인 설명 multi-agent" 시스템의 GraphRAG / Hypothesis / Critic Agent 개발 측
**구현 소스**: `src/wafervlm/schema.py` (pydantic) — 본 문서와 코드가 다르면 코드가 우선, 문서를 갱신할 것

## 1. 역할 경계

VLM은 웨이퍼맵에서 **관측되는 사실만** 출력한다: 패턴 분류, 공간/형상 서술, 구분 근거.
**공정 원인 추론은 하지 않는다** — 원인 후보 생성은 GraphRAG, 증거 수집은 Hypothesis Agent 담당.
`description`에 공정/장비/원인 어휘가 나타나면 계약 위반이다 (`eval/hallucination.py`로 검사).

## 2. 출력 스키마

```json
{
  "patterns": ["Edge-Ring"],
  "spatial": {"zone": "edge", "direction": "전방위", "shape": "ring"},
  "description": "웨이퍼 가장자리를 따라 링 형태로 불량 die가 밀집한다. 불량 die 비율은 약 18.0%이다.",
  "severity": {"defect_die_ratio": 0.18},
  "confidence": "high",
  "ambiguity": null
}
```

| 필드 | 타입 | 통제 어휘 / 규약 |
|---|---|---|
| `patterns` | string[] | 9종: `Center` `Donut` `Edge-Loc` `Edge-Ring` `Loc` `Near-Full` `Scratch` `Random` `None`. 혼합 패턴은 복수 원소. `None`은 단독으로만. **KG 결함 패턴 엔티티와 1:1 매핑** |
| `spatial.zone` | string | `center` / `mid` / `edge` / `full` |
| `spatial.direction` | string | `1시`~`12시` 또는 `전방위` |
| `spatial.shape` | string | `ring` / `line` / `cluster` / `scatter` / `arc` / `blob` / `none` |
| `description` | string | 자연어 관측 서술 (한국어). 원인 언급 금지 |
| `severity.defect_die_ratio` | float | 0.0~1.0, 전체 die 대비 불량 die 비율 |
| `confidence` | string | `high` / `medium` / `low`. calibration은 모델 카드의 ECE 곡선 참조 |
| `ambiguity` | object\|null | 판정이 애매할 때만: `{"candidates": [패턴...], "reason": "..."}`. **Critic Agent의 재검증 요청 트리거로 사용 가능** |

## 3. 에러 규약 (serve/api.py)

`POST /read` 응답:
- 성공: `{"ok": true, "readout": {...}, "raw_answer": "..."}`
- 스키마 위반이 1회 재시도(저온 재샘플) 후에도 지속: `{"ok": false, "error": "schema violation after retry: ...", "raw_answer": "..."}`
  → 호출 측은 이 경우를 "판독 불능"으로 처리하고 원인 분석 파이프라인을 트리거하지 말 것

## 4. 운영 특성

- 추론 파라미터: temperature 0.6 / top_p 0.95 / max_tokens 1024 (Thinking 모델 권장값, 모델 카드에서 최종 확정)
- latency: thinking 토큰 길이에 지배됨 — M4 측정치를 모델 카드에 기재
- 입력: 렌더링 규약(448px nearest, 팔레트)은 `constants.py`의 `RENDER_SIZE`/`RENDER_PALETTE` 참조.
  원본 0/1/2 배열을 보내면 API가 동일 규약으로 렌더링한다 (권장 경로)
