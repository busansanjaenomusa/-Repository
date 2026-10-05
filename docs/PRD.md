# 산재보험 장해보상금(연금·일시금) 계산기 웹앱 개발 명세서 (PRD)

## 1. 프로젝트 개요
* **목적**: 산재 상담 현장에서 재해자의 임금(월급, 일당, 또는 1일 평균임금)과 예상 장해등급(1급~14급)을 입력받아 즉시 장해보상금(일시금, 연금 연액 및 월 실수령액, 선급금 및 선급기간 중 월 지급액)을 오차 없이 계산하는 단일 파일 웹 애플리케이션 개발.
* **사용자 환경**: 산재 전문 노무사 및 실무자가 상담 현장에서 태블릿 또는 모바일·PC 브라우저로 단독 실행.
* **구현 스펙**: 단일 파일 HTML (`index.html`), 외부 라이브러리 최소화(Tailwind CSS CDN + Vanilla JavaScript), 오프라인 로컬 구동 가능 구조.

---

## 2. 연산 규칙 및 법적 파이프라인 (Calculation Pipeline)

[1단계: 임금 입력 및 1일 평균임금 산정]
- 공제입력: 입력값을 1일 평균임금 기준으로 변환
- 계산 방식: 월급 ÷ 30.4167
- 예외 처리:
  - 일당 기준: 통상근로계수 0.73(하한 기준) 적용
  - 일당 기준 + 건설일용근로자 예외: 실제 월 출근일수 기준 환산
  - 직접 입력 시: 입력 금액 그대로 사용

[2단계: 표준보상기준금액 적용 (Clamping)]
- 장해보상금은 36조 7항에서 정한 최고·최저 기준금액을 벗어나지 않도록 제한
- 최저 보상 기준금액: 최저 기준금액 미만일 시 상향 조정
- 최고 보상 기준금액: 최고 기준금액 초과 시 하향 조정

[3단계: 장해등급별 수급 방식 결정]
- 1급 ~ 3급: 연금 우선(일시금 또는 연금 선택 가능)
- 4급 ~ 7급: 선택형(연금 vs 일시금)
- 8급 ~ 14급: 일시금만

[4단계: 선급금 및 선급기간 중 연금 지급 계산]
- 선급금: 연금액의 50% 수준으로 선지급
- 선급기간 중 월 지급: 연금 월 지급액의 50% 감액
- 선급금은 장해등급별 최대 선급 연수 전후로 제한 적용

---

## 3. 데이터 상수 (Constants & Tables)

### 가. 장해등급별 보상금액 테이블 (`DISABILITY_COMPENSATION_TABLE`)

| 장해등급 | 장해보상금 일수 (1년 기준) | 연금/일시금 산정 기준일수 | 수급 방식 | 최대 선급 가능 연수 |
| :---: | :---: | :---: | :---: | :---: |
| **1급** | 329일 | 1,474일 | `PENSION_ONLY` | 4년 (50% 선급) |
| **2급** | 291일 | 1,309일 | `PENSION_ONLY` | 4년 (50% 선급) |
| **3급** | 257일 | 1,155일 | `PENSION_ONLY` | 4년 (50% 선급) |
| **4급** | 224일 | 1,012일 | `SELECTABLE` | 2년 (50% 선급, 연금 선급 시) |
| **5급** | 193일 | 869일 | `SELECTABLE` | 2년 (50% 선급, 연금 선급 시) |
| **6급** | 164일 | 737일 | `SELECTABLE` | 2년 (50% 선급, 연금 선급 시) |
| **7급** | 138일 | 616일 | `SELECTABLE` | 2년 (50% 선급, 연금 선급 시) |
| **8급** | 0일 | 495일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **9급** | 0일 | 385일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **10급** | 0일 | 297일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **11급** | 0일 | 220일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **12급** | 0일 | 154일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **13급** | 0일 | 99일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |
| **14급** | 0일 | 55일 | `LUMP_SUM_ONLY` | 0년 (선급 불가) |

### 나. 연도별 보상기준금액 제한 (`COMPENSATION_LIMITS`)

```javascript
const COMPENSATION_LIMITS = {
  2026: { max: 268299, min: 82560 },
  2025: { max: 258132, min: 80240 },
  2024: { max: 253354, min: 78880 },
  2023: { max: 246036, min: 76960 },
  2022: { max: 232664, min: 73280 },
  2021: { max: 226191, min: 69760 }
};
```

---

## 4. UI/UX 레이아웃 명세

1. 메인 입력 영역

- 장해등급 선택
- 임금 유형 선택
- 임금 금액 입력
- 일용근로자 예외 여부
- 연도 선택
- 선급 연수 입력

2. 계산 결과 영역

- 1일 평균임금
- 장해등급별 보상기준
- 일시금 총액
- 연금 연액
- 월 지급액
- 선급금 총액
- 선급기간 중 월 지급액

3. 추가 동작

- 입력값 수정 시 즉시 결과 갱신
- 각 입력값은 모바일과 태블릿에서 자연스럽게 보이도록 1열/2열 배치
- 결과 값은 통화 형식으로 표시

---

## 5. 핵심 연산 파이프라인 구현 코드 예시

```javascript
/**
 * 산재보험 장해급여 연산 코어 함수
 */
function calculateCompensation({
  year = 2026,
  wageType = 'direct',          // 'direct', 'monthly', 'daily'
  inputAmount = 0,              // 입력 금액(원)
  isDailyWorkerExempt = false,  // 건설일용직 통상근로계수 배제 여부
  dailyWorkDays = 22,           // 배제 시 월 출역일수
  grade = 1,                    // 1 ~ 14
  advanceYears = 0              // 선급 연수 (0: 없음)
}) {
  const limits = COMPENSATION_LIMITS[year] || COMPENSATION_LIMITS[2026];
  const gradeData = DISABILITY_COMPENSATION_TABLE[grade];

  // 1. 1일 평균임금 산정
  let rawDailyWage = 0;
  if (wageType === 'direct') {
    rawDailyWage = Number(inputAmount);
  } else if (wageType === 'monthly') {
    rawDailyWage = Number(inputAmount) / 30.4167;
  } else if (wageType === 'daily') {
    if (isDailyWorkerExempt) {
      // 통상근로계수 적용 제외 시: 실제 월 출역일수 기반 환산
      rawDailyWage = (Number(inputAmount) * Number(dailyWorkDays)) / 30.4167;
    } else {
      // 원칙: 통상근로계수 73% 적용
      rawDailyWage = Number(inputAmount) * 0.73;
    }
  }

  // 2. 최고·최저 보상기준금액 Clamping (산재법 제36조 제7항)
  let finalDailyWage = rawDailyWage;
  let limitStatus = 'NORMAL'; // 'MAX_APPLIED', 'MIN_APPLIED'

  if (finalDailyWage > limits.max) {
    finalDailyWage = limits.max;
    limitStatus = 'MAX_APPLIED';
  } else if (finalDailyWage < limits.min) {
    finalDailyWage = limits.min;
    limitStatus = 'MIN_APPLIED';
  }

  finalDailyWage = Math.round(finalDailyWage);

  // 3. 일시금 및 연금 기본액 산정
  const lumpSumTotal = Math.round(finalDailyWage * gradeData.lumpSum);
  const pensionAnnual = Math.round(finalDailyWage * gradeData.pension);
  const pensionMonthly = Math.round(pensionAnnual / 12);

  // 4. 선급금 및 선급 기간 중 월 연금액 정밀 연산 (산재법 제57조 제5항)
  let advanceAmount = 0;
  let monthlyDuringAdvance = pensionMonthly;
  const validAdvanceYears = Math.min(advanceYears, gradeData.maxAdvanceYears);

  if (gradeData.pension > 0 && validAdvanceYears > 0) {
    // 선급금: 선택 연수분 연금액의 50%
    advanceAmount = Math.round(pensionAnnual * validAdvanceYears * 0.5);
    // 선급 기간 중: 50% 감액된 월 연금 지급
    monthlyDuringAdvance = Math.round(pensionMonthly * 0.5);
  }

  return {
    rawDailyWage: Math.round(rawDailyWage),
    finalDailyWage,
    limitStatus,
    grade,
    gradeType: gradeData.type,
    lumpSumTotal,
    pensionAnnual,
    pensionMonthly,
    advanceYears: validAdvanceYears,
    advanceAmount,
    monthlyDuringAdvance,
    maxAdvanceYears: gradeData.maxAdvanceYears
  };
}
```

---

## 6. 구현 가이드 (GitHub Copilot 참조 문구)

"장해보상금 계산기 웹앱을 구현해줘. 100% 정적 HTML/CSS/JS로 만들고, Tailwind CSS CDN을 활용하며, 휴대폰/태블릿/PC에서 모두 보기 좋게 반응형 UI를 구성해줘. 산재법에 따른 계산 흐름은 1일 평균임금 계산, 최고·최저 보상기준금액 제한, 장해등급별 연금·일시금 구분, 선급금 계산을 반영하고, 코드 주석은 법률 검토가 필요한 부분에 `TODO: 확인 필요`를 남겨줘."

---

## 7. 작업 메모 / 진행 여부

- 명세서와 계산 함수는 문서와 앱 로직에 그대로 반영한다.
- 구현 코드에서 명세서에 없거나 애매한 법리적 세부사항은 추측하지 않고 `TODO: 확인 필요` 주석으로 남긴다.
- 본 문서는 최초 PRD이며, 이후 법률 검토와 입력값 검증을 추가할 수 있다.

