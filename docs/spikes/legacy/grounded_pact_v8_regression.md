# 추천 v8 기본 회귀 원문

추천 프롬프트 v8의 P1~P7 기록을 보존한다. 현재 계약은 [추천 프롬프트](../../../src/travel/prompts/generate_pact.md), 실행 입력은 [입력 자료](../../research/structured_output_inputs.json)의 같은 ID를 따른다.

## v8 입장 추출 회귀 점검 (2026-10-01)

`gpt-6.1-sol`, 추론 `low`, 스키마 v4로 P1~P7의 최초 출력을 각 1회 생성했다. 재생성·재시도는 0회다. 입력 고정부터 생성·자동 검사까지 212초로 15분 상한 안에 종료했다.

JSON·스키마, 상태·응답 ID·원문 인용과 입장 누락·중복 검사를 7/7건 통과했다. `ParticipantPosition`의 네 속성은 온톨로지와 일치한다. 후처리를 실행해 인용의 원문 일치와 공유 제외를 확인하고, `build_position_review`로 선택·메모·추출 입장·추천을 나란히 대조하는 자료를 생성했다. 의미는 원본과 따로 대조하며 이 결과를 사람 합의 품질 점수로 세지 않는다.

| 입력 | 실제 상태 | 자동 검사 |
|---|---|---|
| P1 | `proposed` | 통과 |
| P2 | `needs_information` | 통과 |
| P3 | `proposed` | 통과 |
| P4 | `invalid_input` | 통과 |
| P5 | `unsupported` | 통과 |
| P6 | `conditional_only` | 통과 |
| P7 | `proposed` | 통과 |

전송부 SHA-256: `c052f8b43621261d071c6e7edb16d8f1ef043eb1073d849208d3769c0ff32a1a`. 스키마 SHA-256: `5845d8cace7864421aa45d353fb6b2ee8b925deb416c7bb2c92e6168f550221b`.

<details>
<summary>최초 출력 7건</summary>

### P1

요청 SHA-256: `0baaba152bf64ba7b6b4d528b8d576dbb8d5255508cf06f4a6b743ba4b4569f0`. 출력 SHA-256: `dfeae25479f9e7e1c96f8f0dc6022c16c02eac0346c3797aec97068f1f044168`.

```json
{
  "status": "proposed",
  "clauses": [
    {
      "scenario_id": "free_time",
      "action": "여유 시간에 원하는 활동이 다르면 잠시 따로 지내는 걸 추천해요. A가 충분히 구경할 시간과 B가 혼자 쉴 시간을 확보하고, C는 카페에서 기다리는 방식을 고려해요. B의 휴식 뒤에는 함께 지낼 수도 있도록 각자 필요한 시간을 확인해요. 뒤의 공동 약속을 유지하면서 저녁에 함께 이동할 수 있게 다시 만날 시간과 장소를 정해요.",
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
        "따로 움직이기 전에 각자 필요한 시간과 다시 만날 시간·장소를 정해요.",
        "휴식 뒤 함께 지낼지는 각자의 활동이 끝나는 시점을 확인해 정해요."
      ]
    }
  ],
  "positions": [
    {
      "response_id": "rA",
      "position": {
        "desired_action": "한 시간 이상 구경하고 싶으며 따로 다녀도 괜찮음"
      }
    },
    {
      "response_id": "rB",
      "position": {
        "desired_action": "한 시간은 혼자 쉬고 싶으며 그 뒤에는 함께 있어도 괜찮음"
      }
    },
    {
      "response_id": "rC",
      "position": {
        "desired_action": "카페에서 기다려도 괜찮으며 저녁에는 함께 가고 싶음"
      }
    }
  ]
}
```

### P2

요청 SHA-256: `2d49ca67bd924cbf1667801b86ca2e10f9b58296cabfec48c9f29057a244610d`. 출력 SHA-256: `19f9a75098d547ffee857c9cb1d81934a0b3feb690da3637d925ba3e941316bb`.

```json
{
  "status": "needs_information",
  "clauses": null,
  "positions": [],
  "message": "채택된 제출 건 C의 free_time 응답이 빠져 있어 추천 조항을 만들 수 없어요."
}
```

### P3

요청 SHA-256: `34bc18a855c66691b256aef1f0712806a6e3934783096a0379a4bd0f4dc1a3c2`. 출력 SHA-256: `7938191942cb2fd3133ab8fe68ce5b4d1363de5de1813b67cdf6bb757d3650f8`.

```json
{
  "status": "proposed",
  "clauses": [
    {
      "scenario_id": "free_time",
      "action": "여유 시간에 쉬는 방식이 다르면 B는 혼자 쉴 시간을 갖고 C는 카페에서 기다리는 방식을 추천해요. B가 필요한 휴식을 마친 뒤 함께할지는 두 사람이 정하고, 함께하는 저녁 일정에 맞춰 다시 만나요. 따로 움직이기 전에 필요한 시간과 합류 장소를 정해요.",
      "participant_ids": ["B", "C"],
      "source_response_ids": ["rB", "rC"],
      "proposed_conditions": [
        "따로 움직이기 전에 각자 필요한 시간과 합류 장소를 정해요.",
        "휴식이 끝난 뒤 함께할지는 B와 C가 정해요."
      ]
    }
  ],
  "unresolved_conditions": [
    {
      "scenario_id": "free_time",
      "source_response_ids": ["rA"],
      "description": "A가 피하려는 대상이 확인되지 않아 A의 응답은 이번 추천에 적용하지 않았어요."
    }
  ],
  "positions": [
    {
      "response_id": "rA",
      "position": {"desired_action": "구경을 선택했지만 피하려는 대상은 확인되지 않음"}
    },
    {
      "response_id": "rB",
      "position": {"desired_action": "한 시간은 혼자 쉬고 싶으며 그 뒤에는 함께 있어도 괜찮음"}
    },
    {
      "response_id": "rC",
      "position": {"desired_action": "카페에서 기다려도 괜찮고 저녁에는 함께 가고 싶음"}
    }
  ]
}
```

### P4

요청 SHA-256: `58961d4f506e2c96f63a245194a8a04e732d06d585c65a42c8ffdf159460ce35`. 출력 SHA-256: `31468a32b8ea917b2562e1102bf6c0df79bedbebbab4bfe6412d5744adb7979a`.

```json
{
  "status": "invalid_input",
  "clauses": null,
  "positions": [],
  "message": "rA가 선택한 nonexistent는 free_time 문항에 없는 선택지예요."
}
```

### P5

요청 SHA-256: `2541f4702cf9b76e7528d684e7ba912bd4e1a115426eb30e38b9505982440c63`. 출력 SHA-256: `b8c929234ae7b6ae19aa8bf296e04f8df9551070007a8ca0c19f2eee722ab386`.

```json
{
  "status": "unsupported",
  "clauses": null,
  "positions": [],
  "message": "궁합을 점수로 평가하는 요청은 지원하지 않아요. 여행 상황에서 각자의 희망과 한계를 조율하는 추천 조항을 만드는 요청만 지원해요."
}
```

### P6

요청 SHA-256: `8e36c27ec2215775829edfbbb496d673f33be49d70c975e15c7368d522d57864`. 출력 SHA-256: `e1c014b40391d08807222647e0513cbd404cb2172a5a2c210e00b04d40c3356e`.

```json
{
  "status": "conditional_only",
  "clauses": null,
  "positions": [
    {
      "response_id": "R12_r1",
      "position": {
        "desired_action": "왼쪽 목적지만 모두 함께 방문하고 싶으며 다른 목적지는 원하지 않고 추가 비용을 낼 수 없음"
      }
    },
    {
      "response_id": "R12_r2",
      "position": {
        "desired_action": "오른쪽 목적지만 모두 함께 방문하고 싶으며 다른 목적지는 원하지 않고 추가 비용을 낼 수 없음"
      }
    },
    {
      "response_id": "R12_r3",
      "position": {
        "desired_action": "목적지는 어느 쪽이든 괜찮지만 차량을 나누거나 따로 기다리지 않고 함께 이동하고 싶으며 추가 비용을 내지 않음"
      }
    }
  ],
  "conditional_alternatives": [
    {
      "scenario_id": "shared_vehicle",
      "action": "공동 차량 한 대로 이동하며 목적지 의견이 다를 때, sub_2가 방문 방향을 바꾸는 데 동의한다면 sub_1이 원하는 왼쪽 목적지로 세 사람이 함께 가는 안을 제안해요. sub_3의 함께 이동하려는 조건과 세 사람의 추가 비용 제한은 유지해요.",
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
        "목적지 제한을 바꾸는 동의가 확인된 뒤에 함께 갈 장소를 정해요."
      ],
      "required_changes": [
        {
          "source_response_id": "R12_r2",
          "original_condition": "나는 오른쪽 목적지만 가고 싶고 왼쪽이나 제3의 장소는 원하지 않아.",
          "proposed_change": "방문 방향을 오른쪽으로 한정하는 조건을 완화해 왼쪽 목적지로 함께 이동하는 안을 제안해요. 추가 비용을 내지 않는 조건은 유지해요."
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
      "description": "sub_1과 sub_2가 허용하는 목적지가 다르고 sub_3는 분리 이동과 별도 대기를 원하지 않아요. 세 사람의 추가 비용 제한도 유지해야 해서 원래 조건에 맞는 공동 이동안은 정하지 못했어요."
    }
  ],
  "message": "한 곳으로 공동 이동하기, 별도 차량으로 나누기, 다른 장소 고르기를 검토했어요. 목적지와 분리 이동, 추가 비용 제한이 남아 있어 목적지 제한을 완화하는 조건부 안을 제안해요. 변경이 수락된 것은 아니에요."
}
```

### P7

요청 SHA-256: `be413bf1b47c56f7662e0212296c4950b656a93c86f09fee3fb3204468ef6599`. 출력 SHA-256: `7a463275d258c0d4d665a2898c96909ba55f4bab14301cc5845ce5d07234a310`.

```json
{
  "status": "proposed",
  "clauses": [
    {
      "scenario_id": "free_time",
      "action": "여유 시간에 원하는 휴식이 다르면 잠시 따로 보내는 걸 추천해요. A는 긴 도보 이동을 피하며 카페에서 쉬고, C도 카페에서 기다릴 수 있어요. B는 숙소에서 한 시간 혼자 쉬는 시간을 확보해요. 그 뒤 함께할지는 다시 정하고, 저녁 약속은 유지하도록 재합류 방법을 정해요.",
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
        "A가 오래 걷지 않아도 되는 이동 방법을 정해요.",
        "B의 혼자 쉬는 시간이 끝난 뒤 함께할지 정해요.",
        "저녁 약속을 지킬 수 있도록 재합류 시간과 장소를 정해요."
      ]
    }
  ],
  "positions": [
    {
      "response_id": "rA",
      "position": {
        "desired_action": "오래 걷기 어려워 지금은 카페에서 쉬고 싶으며 다른 일행은 따로 구경해도 괜찮음",
        "condition": "오래 걸으면 무릎이 아파.",
        "reason": "많이 걷기 힘들어서",
        "expressed_content": "많이 걷기 힘들어서 카페에서 쉬고 싶어"
      }
    },
    {
      "response_id": "rB",
      "position": {
        "desired_action": "숙소에서 한 시간 혼자 쉬고 싶으며 그 뒤에는 함께 있어도 괜찮음"
      }
    },
    {
      "response_id": "rC",
      "position": {
        "desired_action": "카페에서 기다려도 괜찮으며 저녁에는 함께 가고 싶음"
      }
    }
  ]
}
```

</details>
