# DWEB 게시판

Next.js 16 (App Router) · TypeScript · shadcn/ui로 만든 웹 게시판입니다.

## 실행

`.env.local`에 Neon 연결 문자열을 넣습니다 (git에 올라가지 않음).

```env
# 앱용: 풀링 연결 (호스트에 -pooler)
DATABASE_URL="postgresql://...-pooler.../neondb?sslmode=verify-full&channel_binding=require"
# 마이그레이션용: 직접 연결 (-pooler 없음)
DATABASE_URL_UNPOOLED="postgresql://.../neondb?sslmode=verify-full&channel_binding=require"
```

```bash
npm install
npm run db:migrate   # 테이블 생성 (처음 한 번, 스키마 변경 시)
npm run db:seed      # 글이 없으면 환영 공지 추가
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
| `src/lib/board.ts` | 조회 쿼리 (목록·검색·상세) |
| `src/lib/actions.ts` | 서버 액션 (작성·수정·삭제, 입력 검증) |
| `src/db/schema.ts` | Drizzle 스키마 (`posts`, `comments`) |
| `drizzle/` | 생성된 SQL 마이그레이션 |
| `src/components/ui` | shadcn/ui 컴포넌트 |

## 데이터

게시글과 댓글은 Neon Postgres에 저장됩니다 (Drizzle ORM + `pg`).
글을 지우면 댓글도 외래 키(`ON DELETE CASCADE`)로 함께 지워집니다.
시드로 넣는 환영 공지의 비밀번호는 `admin1234`입니다.

스키마를 바꿀 때는 `src/db/schema.ts`를 고친 뒤 `npm run db:generate`로 마이그레이션을 만들고
`npm run db:migrate`로 적용합니다.
