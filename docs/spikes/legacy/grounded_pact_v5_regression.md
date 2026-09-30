# v5 원문 공개 경계 회귀 점검 (2026-09-30)

보존 출처: 커밋 `d9be58ca489e7c5264e8e065e2e537f30fc52378`의 `src/travel/prompts/generate_pact.md`에 기록된 v5 회귀 점검. 입력·출력·측정값을 유지하고 참조 경로를 현재 저장 위치에 맞췄다.

`gpt-6.1-sol`, 추론 수준 `low`, 스키마 v3으로 기본 다섯 유형과 조건부 대안 1건의 최초 출력을 생성했다. 재시도·재생성은 0회이다. 입력 고정부터 저장·자동 검사까지 23:19:00~23:21:22 KST, 142초로 15분 상한 안에 종료했다. 서비스 API 지연·화면 구현 검증과는 구분한다.

P1~P5는 [재현 입력](../../research/structured_output_inputs.json)의 같은 ID를 사용하며, P6는 [추천 실험 R12](grounded_pact_v4_outputs.jsonl)의 공동 차량 입력을 사용했다. 기존 회차의 결과와 별도로 기록한다.

| 입력 | 유형 | 실제 상태 | 자동 검사 |
|---|---|---|---|
| v5-P1 | 정상 | `proposed` | 통과 |
| v5-P2 | 응답 누락 | `needs_information` | 통과 |
| v5-P3 | 모호한 메모 | `proposed` | 통과 |
| v5-P4 | 없는 선택지 | `invalid_input` | 통과 |
| v5-P5 | 지원 밖 요청 | `unsupported` | 통과 |
| v5-P6 | 조건부 대안의 원문·공유 문장 분리 | `conditional_only` | 통과 |

6건 모두 JSON·스키마·상태·참조 검사를 통과했다. P6는 `original_condition`에 정확한 메모 인용을 남기고, `action`과 `proposed_change`에는 조건 변경을 풀어 썼다. 검증용 필드를 제외한 출력에서 12자 이상 메모 문장의 완전 복사는 발견되지 않았다. 서버의 실제 공유 응답·이미지 처리는 AC3·AC13으로 확인한다. 독립 의미 대조에서는 P3의 제외 사유에 부정어가 빠진 문장 1건을 확인했다. 상태·근거·제외 대상은 맞았으며 최초 출력은 그대로 보존했다.

전송부 SHA-256: `3b63c2dc3bc39fad7c0aaf33f366bb8b067d6f649d66c40591e1f4aeddc72595`. 스키마 파일 SHA-256: `9146f076c5abdc1d95aadbf629ad6ec9a5947c5ba29fbc4e8204deba6e866b54`.

<details>
<summary>v5 최초 출력 6건</summary>

### v5-P1: 정상

요청 SHA-256: `e57c9c0f5b42ca2059d7e66d471a72ed16c9586bd33a1b26c21170e8da972df4`. 출력 SHA-256: `77a297ee4a9c96716e4daa4af598298097a38b2a1267d0a4e1324b17e3ccf14d`.

```json
{
  "status": "proposed",
  "clauses": [
    {
      "scenario_id": "free_time",
      "action": "여유 시간이 생겨 구경과 휴식 의견이 갈리면 A가 구경할 시간과 B가 혼자 쉴 시간을 확보하도록 잠시 따로 보내는 방식을 제안한다. C는 카페에서 기다리는 방식을 선택할 수 있다. 나뉘기 전에 각자 필요한 시간을 확인하고, 이후 함께할 약속을 유지할 수 있도록 다시 만날 시각과 장소를 정한다.",
      "participant_ids": [
        "A",
        "B",
        "C"
      ],
      "source_response_ids": [
        "rA",
        "rB",
        "rC"
      ],
      "proposed_conditions": [
        "따로 보내기 전에 각자 필요한 시간과 재합류 시각·장소를 함께 정한다."
      ]
    }
  ]
}
```

### v5-P2: 응답 누락

요청 SHA-256: `75c46aa02fe327e11a03424fc9e771eb67c5ed9555e389beccde0a2572d8c704`. 출력 SHA-256: `36ef2f31bf25e0eab5759a402fe19ce1fbede826d430d662a09ee5faf76bd590`.

```json
{
  "status": "needs_information",
  "clauses": null,
  "message": "채택된 제출 건 C의 free_time 응답이 입력에서 누락되었습니다."
}
```

### v5-P3: 모호한 메모

요청 SHA-256: `674344d11efaa25c850e6c2cc5473ed243feb2b508b611e44de3ad1db41df192`. 출력 SHA-256: `70f39b9e6e6a4d453be2627cfa125a342a0af92f4d5b3e9b857c23928e858d98`.

```json
{
  "status": "proposed",
  "clauses": [
    {
      "scenario_id": "free_time",
      "action": "여유 시간이 생겨 휴식과 카페 이용 의견이 나뉘면 B가 혼자 쉬는 데 필요한 시간을 확보하고 C는 카페에서 기다리는 방식을 제안한다. B가 휴식을 마친 뒤 함께 시간을 보내는 것은 선택할 수 있으며, 저녁 약속에는 함께 갈 수 있도록 나뉘기 전에 필요한 시간과 다시 만날 시각·장소를 정한다.",
      "participant_ids": [
        "B",
        "C"
      ],
      "source_response_ids": [
        "rB",
        "rC"
      ],
      "proposed_conditions": [
        "따로 보내기 전에 필요한 시간과 재합류 시각·장소를 정한다."
      ]
    }
  ],
  "unresolved_conditions": [
    {
      "scenario_id": "free_time",
      "source_response_ids": [
        "rA"
      ],
      "description": "A가 피하려는 대상이 입력에 없어 구경 선택의 적용 조건을 확인할 수 있으므로 해당 응답은 추천 적용 대상에서 제외한다."
    }
  ]
}
```

### v5-P4: 없는 선택지

요청 SHA-256: `84c4600405a5593db2f5f5cc23afc0929a302420d9404d026fbf297707ab7615`. 출력 SHA-256: `a902ecd7be81150976e6e832f8cc90b2c393db60c77e7578e4a160ae035f35de`.

```json
{
  "status": "invalid_input",
  "clauses": null,
  "message": "rA의 선택지 ID nonexistent는 free_time 문항에 존재하지 않습니다."
}
```

### v5-P5: 지원 밖 요청

요청 SHA-256: `6a41311f9cc3483078a5f4a3603946a364e637f4ea020f3319cc2889068081f8`. 출력 SHA-256: `5502f1d5c9446b8549c458b1841e34fa78df7d579ec1a545ce1d1a587eeb1ce4`.

```json
{
  "status": "unsupported",
  "clauses": null,
  "message": "궁합을 점수로 평가하는 요청은 지원하지 않습니다. 가상 상황의 응답으로는 비슷한 상황에서 사용할 조율 조항을 추천할 수 있습니다."
}
```

### v5-P6: 조건부 대안의 원문·공유 문장 분리

요청 SHA-256: `047204bb620c98ceca6c19c0dfd446b25ef85d70fa5f793d74705ed4aabd09ae`. 출력 SHA-256: `f16c35b8fb3ca33c0c1ae459baae9af74536f63d80a5f26808a03de56b13cf7b`.

```json
{
  "status": "conditional_only",
  "clauses": null,
  "conditional_alternatives": [
    {
      "scenario_id": "shared_vehicle",
      "action": "공동 차량으로 서로 다른 방향의 목적지를 원하는 상황에서, sub_2가 목적지 제한을 완화하는 경우 sub_1이 원하는 방향으로 모두 함께 이동하는 방식을 제안한다. sub_1과 sub_2의 추가 비용 한계, sub_3의 함께 이동하려는 조건을 유지하며 변경이 수락되기 전에는 이 방식을 확정하지 않는다.",
      "participant_ids": [
        "sub_1",
        "sub_2",
        "sub_3"
      ],
      "source_response_ids": [
        "R12_r1",
        "R12_r2",
        "R12_r3"
      ],
      "proposed_conditions": [
        "목적지 제한 변경이 수락된 경우에만 공동 차량으로 함께 이동할 목적지를 정한다."
      ],
      "required_changes": [
        {
          "source_response_id": "R12_r2",
          "original_condition": "나는 오른쪽 목적지만 가고 싶고 왼쪽이나 제3의 장소는 원하지 않아.",
          "proposed_change": "sub_1이 원하는 방향의 목적지도 함께 이동할 후보로 허용하는 변경을 제안한다."
        }
      ]
    },
    {
      "scenario_id": "shared_vehicle",
      "action": "공동 차량으로 서로 다른 방향의 목적지를 원하는 상황에서, sub_1이 목적지 제한을 완화하는 경우 sub_2가 원하는 방향으로 모두 함께 이동하는 방식을 제안한다. sub_1과 sub_2의 추가 비용 한계, sub_3의 함께 이동하려는 조건을 유지하며 변경이 수락되기 전에는 이 방식을 확정하지 않는다.",
      "participant_ids": [
        "sub_1",
        "sub_2",
        "sub_3"
      ],
      "source_response_ids": [
        "R12_r1",
        "R12_r2",
        "R12_r3"
      ],
      "proposed_conditions": [
        "목적지 제한 변경이 수락된 경우에만 공동 차량으로 함께 이동할 목적지를 정한다."
      ],
      "required_changes": [
        {
          "source_response_id": "R12_r1",
          "original_condition": "나는 왼쪽 목적지만 가고 싶고 오른쪽이나 제3의 장소는 원하지 않아.",
          "proposed_change": "sub_2가 원하는 방향의 목적지도 함께 이동할 후보로 허용하는 변경을 제안한다."
        }
      ]
    }
  ],
  "unresolved_conditions": [
    {
      "scenario_id": "shared_vehicle",
      "source_response_ids": [
        "R12_r1",
        "R12_r2",
        "R12_r3"
      ],
      "description": "sub_1과 sub_2는 서로 다른 방향의 목적지만 허용하면서 추가 비용을 부담할 수 없고, sub_3는 이동을 나누거나 따로 기다리는 방식을 허용하지 않는다. 원래 조건을 유지하는 함께 이동·분리 이동·대체 목적지 방식은 구성하지 못했다."
    }
  ],
  "message": "함께 이동, 별도 차량 이용, 따로 기다리기와 다른 목적지 선택을 검토했으나 목적지 제한·추가 비용 한계·함께 이동 조건이 막혔다. 목적지 제한을 완화하는 두 대안을 제안했으며 변경 수락 여부는 확인되지 않았다."
}
```

</details>
