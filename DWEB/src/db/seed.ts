// 게시글이 하나도 없을 때 환영 공지를 넣는다: npm run db:seed
import { config } from "dotenv"

config({ path: ".env.local" })

async function main() {
  const { db } = await import("./index")
  const { posts } = await import("./schema")
  const { hashPassword } = await import("../lib/password")

  if ((await db.$count(posts)) > 0) {
    console.log("이미 게시글이 있어 시드를 건너뜁니다.")
  } else {
    await db.insert(posts).values({
      category: "공지",
      title: "DWEB 게시판에 오신 것을 환영합니다",
      content:
        "자유롭게 글을 남겨 주세요.\n\n글을 쓸 때 입력한 비밀번호로 글과 댓글을 수정하거나 삭제할 수 있습니다.",
      author: "관리자",
      passwordHash: hashPassword("admin1234"),
    })
    console.log("환영 공지를 추가했습니다.")
  }
  process.exit(0)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
