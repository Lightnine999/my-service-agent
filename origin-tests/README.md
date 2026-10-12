# 원천 실험 기록 — get_inventory_tool · qdrant_rag_test

이 설계의 출발점이 된 두 실습 폴더의 테스트를 기록한다. 두 폴더는 이 저장소 밖(`~/aiffel_work/get_inventory_tool`, `~/aiffel_work/qdrant_rag_test`)에 있고, 여기에는 실행 결과 원문과 요약만 옮겼다.

| 폴더 | 실습 | 이 설계에 준 것 |
|---|---|---|
| `get_inventory_tool` | 도구 정의 + 하네스로 잘못된 호출 막기 | 도구 계약 형식, 질문 대조 규칙, 응답 필터, 재시도 상한 |
| `qdrant_rag_test` | 남이 만든 MCP 서버(Qdrant RAG) 붙이기 | `search_policy`의 한계(유사도 점수 없음)와 설정이 도구 정의를 바꾼다는 점 |

## 1. get_inventory_tool

창고 재고 조회 도구 `get_inventory`(읽기 전용, 허용 창고 `SEOUL-01`·`BUSAN-02`)에 하네스를 붙여 실패 사례 3건을 막는 실습이다. 도구 구현은 가짜이며 어떤 SKU를 넣어도 수량 7을 돌려준다.

### 테스트 구성

| 테스트 | 내용 | 결과 원문 |
|---|---|---|
| 회귀 테스트 `test_regression.py` | 실패 사례 3건(허용되지 않은 창고, SKU 없음·지어냄, 원가 노출)과 대조군 4건, 총 11개 | [`get_inventory/regression-test.txt`](get_inventory/regression-test.txt) |
| 변형 실험 `mutation_check.py` | 하네스를 일부러 망가뜨린 변형 M1~M6에서 테스트가 실패하는지 확인 | [`get_inventory/mutation-check.txt`](get_inventory/mutation-check.txt) |
| 모델 실행 트레이스 | 로컬 모델 `qwen3.5:2b`(온도 0)로 정상 질문·실패 사례 실행 | [`../my-agent/traces/`](../my-agent/traces/) (`trace-01` ~ `trace-10`, `SUMMARY.md`) |

### 결과 (2026-10-12 재실행)

- 회귀 테스트: **11개 모두 통과**
- 변형 실험: 변형 없는 기준선은 통과, **M1~M6는 모두 실패** (테스트가 하네스 고장을 잡아낸다는 뜻)

| 변형 | 망가뜨린 것 | 실패한 테스트 수 |
|---|---|---|
| M1 | SKU 검증 제거 | 2 |
| M2 | 창고 enum 검증 제거 | 1 |
| M3 | 응답 필터 제거 (원가 노출) | 1 |
| M4 | 재시도 상한 제거 | 1 |
| M5 | 검증 우회 (검증 실패도 호출) | 5 |
| M6 | 질문 대조 규칙 제거 (지어낸 SKU 통과) | 2 |

### 한계

- 회귀 테스트와 변형 실험은 하네스 계층만 확인한다. 모델의 판단은 검증하지 않는다.
- 트레이스 `trace-06` ~ `trace-10`은 응답 필터 버그(재고 수량 필드까지 지움)가 있던 상태의 기록이다. 버그를 고친 뒤 `scorecard_run.py v1`로 세트 전체(실패 사례 3건 + 정상 1건)를 다시 돌린 `trace-11`에서 수량이 돌아왔다. 판정은 `../my-agent/traces/scorecard.md`에 있다.
- 모든 트레이스는 질문당 1회 실행이다.

## 2. qdrant_rag_test

공개 MCP 서버 `mcp-server-qdrant`를 Claude Code에 `.mcp.json`으로 붙인 실습이다.

현재 설정:

| 환경변수 | 값 |
|---|---|
| `QDRANT_URL` | `:memory:` (서버를 끄면 데이터가 사라짐) |
| `COLLECTION_NAME` | `policies` |
| `EMBEDDING_PROVIDER` | `fastembed` |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` |

### 테스트 구성

| 테스트 | 내용 | 결과 원문 |
|---|---|---|
| 연결 테스트 `qdrant_mcp_test.py` | `.mcp.json` 설정으로 서버를 띄우고 MCP 프로토콜로 `initialize` → `tools/list` → `qdrant-store` → `qdrant-find` 순서로 호출. `.mcp.json`이 있는 폴더에서 실행 | [`qdrant/connection-test.txt`](qdrant/connection-test.txt) |

### 결과

- **연결 테스트 (2026-10-12 재실행):** 초기화 성공, 도구 `qdrant-find`·`qdrant-store` 확인, 문장 1개 저장 후 검색에서 같은 문장과 메타데이터가 돌아옴. 테스트 문장은 연결 확인용 예시(연차 규정)이며 서비스 내용과 관계없다. 저장한 문장이 하나뿐이라 검색 순위의 품질은 이 테스트로 알 수 없다.
- **환경변수 이름 오류 (서버 소스 `settings.py`로 확인):** 노드에서 받은 설정의 `QDRANT_COLLECTION`·`EMBEDDER_PROVIDER`·`FASTEMBED_MODEL`은 서버가 읽지 않는 이름이었다. 실제 이름은 `COLLECTION_NAME`·`EMBEDDING_PROVIDER`·`EMBEDDING_MODEL`이다. 이름이 틀리면 오류 없이 기본값으로 동작해서 알아채기 어렵다.
- **설정이 도구 정의를 바꾼다 (서버 소스 `mcp_server.py`로 확인):** `COLLECTION_NAME`이 있으면 서버가 `collection_name` 인자를 미리 채우고 도구 정의에서 지운다. 같은 서버라도 설정에 따라 모델이 쓸 수 있는 인자가 달라진다.

### 이전 세션 기록에만 있는 결과 (원문 출력 없음)

아래는 이전 작업 세션의 인계 메모에 적힌 결과다. 실행 출력 원문이 남아 있지 않아 이번에 다시 확인하지 못했다.

- `qdrant-find`는 유사도 점수를 돌려주지 않고 점수 하한도 없어서, 관련 없는 결과도 같은 형식으로 돌아온다.
- 임베딩 모델 비교 (질문 3개: 환불 기한 / 언제 받을 수 있어 / 택배 언제 와)

| 모델 | 맞힌 질문 | 비고 |
|---|---|---|
| `BAAI/bge-small-en-v1.5` | 2/3 | "택배 언제 와" 실패 |
| `paraphrase-multilingual-mpnet-base-v2` | 2/3 | "택배"는 해결, "언제 받을 수 있어?"가 회귀 |

세 질문을 모두 맞힌 모델은 없었다.

## 이 설계에 반영한 것

| 실험 결과 | `design-packet.md` 반영 |
|---|---|
| 하네스의 질문 대조 규칙만이 지어낸 SKU를 막았다 (M6) | 결제번호는 고객 말이나 조회 결과에 나온 값만 쓴다 (시스템 지시 3번), 서버가 세션 계정을 다시 확인 (`ACCOUNT_MISMATCH`) |
| 재시도 상한을 지우면 테스트가 실패한다 (M4) | 일시적 오류만 1회 재시도, 쓰기 도구는 자동 재시도 금지 |
| 응답 필터 버그로 필요한 수량까지 지워졌다 | ⑤에 반환하지 않을 필드와 반환할 필드를 함께 명시 |
| 검색 결과에 유사도 점수와 하한이 없다 | `search_policy`가 근거를 못 찾으면 `NO_MATCH`로 돌려주고, 근거 없이 답하지 않는다 (④ 보류 조건) |
| 설정에 따라 도구 인자가 바뀐다 | `get_purchase`에서 계정 인자를 아예 없애고 하네스가 세션 계정을 붙인다 |

## 다시 실행하는 방법

```bash
cd ~/aiffel_work/get_inventory_tool
python3 -m unittest test_regression -v
python3 mutation_check.py
```

```bash
cd ~/aiffel_work/qdrant_rag_test
python3 -I <이 저장소>/origin-tests/qdrant/qdrant_mcp_test.py
```

Qdrant 연결 테스트에는 `uvx`가 필요하고, 첫 실행 때 임베딩 모델을 내려받는다.
