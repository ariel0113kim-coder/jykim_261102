// 사이트 콘텐츠. 이 파일만 수정하면 페이지 내용이 갱신된다.
window.PROFILE = {
  name: "홍길동",
  title: "차량 전장 시스템 검증 엔지니어",
  tagline: "요구사항에서 차량까지, 신호 하나도 놓치지 않는 검증을 합니다.",
  email: "aaa@gmail.com",
  resumeUrl: "", // 예: "resume.pdf" — 비워두면 버튼이 숨겨짐
  links: [
    // { label: "GitHub", url: "https://github.com/..." },
    // { label: "LinkedIn", url: "https://linkedin.com/in/..." },
  ],

  about: {
    years: "N년",
    paragraphs: [
      "차량 제어기(ECU)의 기능·통신·진단 검증을 담당하는 전장 검증 엔지니어입니다. 요구사항 분석부터 테스트 설계, HILS 기반 검증, 결함 분석과 리포트까지 검증 전 과정을 수행합니다.",
      "반복되는 검증은 자동화하고, 사람은 더 어려운 시나리오에 집중해야 한다고 믿습니다. CAPL과 Python으로 테스트 자동화 환경을 구축해 검증 효율을 높여 왔습니다.",
    ],
    highlights: [
      { value: "N년+", label: "전장 검증 경력" },
      { value: "N+", label: "검증 프로젝트" },
      { value: "N,000+", label: "작성 테스트 케이스" },
    ],
  },

  // level: 3 = 실무 주도, 2 = 실무 사용, 1 = 기초
  skills: [
    {
      category: "통신 프로토콜",
      items: [
        { name: "CAN / CAN-FD", level: 3 },
        { name: "LIN", level: 3 },
        { name: "UDS (ISO 14229)", level: 3 },
        { name: "Automotive Ethernet", level: 2 },
        { name: "DoIP", level: 2 },
        { name: "FlexRay", level: 1 },
      ],
    },
    {
      category: "검증 툴",
      items: [
        { name: "Vector CANoe / CANalyzer", level: 3 },
        { name: "CAPL", level: 3 },
        { name: "HILS / SILS", level: 2 },
        { name: "dSPACE", level: 2 },
        { name: "Trace32", level: 1 },
      ],
    },
    {
      category: "검증 방법론",
      items: [
        { name: "요구사항 기반 테스트", level: 3 },
        { name: "회귀 테스트", level: 3 },
        { name: "블랙박스 / 화이트박스 테스트", level: 2 },
        { name: "테스트 자동화", level: 3 },
      ],
    },
    {
      category: "표준 / 프로세스",
      items: [
        { name: "ISO 26262", level: 2 },
        { name: "ASPICE", level: 2 },
        { name: "AUTOSAR", level: 1 },
      ],
    },
    {
      category: "자동화 / 스크립트",
      items: [
        { name: "Python", level: 3 },
        { name: "CAPL", level: 3 },
        { name: "CI 연동 테스트", level: 2 },
      ],
    },
    {
      category: "관리 도구",
      items: [
        { name: "JIRA", level: 3 },
        { name: "Polarion", level: 2 },
        { name: "DOORS", level: 2 },
      ],
    },
  ],

  experience: [
    {
      company: "회사명",
      role: "전장 검증 엔지니어 (선임)",
      period: "20XX.XX – 현재",
      achievements: [
        "ADAS 제어기 통신·진단 검증 리드",
        "CAPL 기반 자동화 테스트 환경 구축으로 회귀 검증 시간 단축",
        "양산 전 결함 사전 검출 및 협력사 이슈 대응",
      ],
    },
    {
      company: "이전 회사명",
      role: "전장 검증 엔지니어",
      period: "20XX.XX – 20XX.XX",
      achievements: [
        "BCM 기능 검증 및 테스트 케이스 설계",
        "HILS 환경 구성 및 시험 사양서 작성",
      ],
    },
  ],

  projects: [
    {
      name: "ADAS ECU 통신·진단 검증",
      period: "20XX – 20XX",
      system: "ADAS ECU",
      role: "검증 리드 · CAN-FD 통신 및 UDS 진단 검증",
      tools: ["CANoe", "CAPL", "HILS", "JIRA"],
      results: ["테스트 케이스 N건 설계", "결함 N건 사전 검출"],
    },
    {
      name: "BCM 기능 검증 자동화",
      period: "20XX – 20XX",
      system: "BCM (Body Control Module)",
      role: "자동화 환경 구축 · 회귀 테스트 설계",
      tools: ["CANoe", "Python", "CI"],
      results: ["회귀 검증 시간 X% 단축", "야간 자동 회귀 테스트 운영"],
    },
    {
      name: "BMS 진단 기능 검증",
      period: "20XX – 20XX",
      system: "배터리 관리 시스템",
      role: "UDS 진단 서비스 및 DTC 검증",
      tools: ["CANoe", "UDS", "Polarion"],
      results: ["진단 서비스 N종 검증", "요구사항 추적성 100% 확보"],
    },
  ],

  certifications: [
    { name: "ISTQB CTFL", issuer: "ISTQB", year: "20XX" },
    { name: "ISO 26262 기능안전 교육 이수", issuer: "교육기관", year: "20XX" },
    { name: "Vector CANoe 교육 이수", issuer: "Vector", year: "20XX" },
  ],
};
