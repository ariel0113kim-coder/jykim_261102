# DWEB 게시판

Next.js 16 (App Router) · TypeScript · shadcn/ui로 만든 웹 게시판입니다.

## 실행

```bash
npm install
npm run dev
```

브라우저에서 http://localhost:3000 을 엽니다.

## 기능

- 글 목록: 분류 탭(공지/자유/질문/정보), 검색(제목·내용·작성자), 페이지 이동(10개씩), 공지 상단 고정
- 글쓰기 / 상세 / 수정 / 삭제
- 댓글 작성 / 삭제
- 로그인 없이 글·댓글을 쓸 때 정한 비밀번호로 수정·삭제 (비밀번호는 scrypt 해시로 저장)
- 다크 모드, 모바일 대응

## 구조

| 경로 | 내용 |
|------|------|
| `src/app/page.tsx` | 글 목록 |
| `src/app/posts/new` | 글쓰기 |
| `src/app/posts/[id]` | 글 상세 + 댓글 |
| `src/app/posts/[id]/edit` | 글 수정 |
| `src/lib/board.ts` | 데이터 저장소 (JSON 파일) |
| `src/lib/actions.ts` | 서버 액션 (작성·수정·삭제, 입력 검증) |
| `src/components/ui` | shadcn/ui 컴포넌트 |

## 데이터

게시글은 `data/board.json`에 저장됩니다. 파일이 없으면 첫 요청 때 환영 공지 하나로 새로 만들어집니다.
(환영 공지 비밀번호: `admin1234`) `data/`는 git에서 제외되어 있습니다.

JSON 파일 저장은 서버 한 대에서 돌리는 용도입니다. Vercel 같은 서버리스 환경에 배포하려면
`src/lib/board.ts`를 데이터베이스(예: PostgreSQL, SQLite)로 바꿔야 합니다.
