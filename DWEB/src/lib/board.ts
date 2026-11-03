import { and, asc, desc, eq, ilike, or, sql, type SQL } from "drizzle-orm"
import { connection } from "next/server"
import { db } from "@/db"
import { comments, posts } from "@/db/schema"
import type { Category } from "@/lib/categories"

export { CATEGORIES, type Category } from "@/lib/categories"

export const PAGE_SIZE = 10

// 클라이언트로 보내도 되는 형태 (비밀번호 해시 제외, 날짜는 ISO 문자열)
export type PublicComment = {
  id: number
  author: string
  content: string
  createdAt: string
}

export type PostSummary = {
  id: number
  category: Category
  title: string
  author: string
  createdAt: string
  updatedAt: string | null
  commentCount: number
}

export type PublicPost = Omit<PostSummary, "commentCount"> & {
  content: string
  comments: PublicComment[]
}

const iso = (d: Date | null) => (d ? d.toISOString() : null)

// LIKE 패턴의 특수문자를 그대로 검색되도록 이스케이프
const likePattern = (q: string) => `%${q.replace(/[\\%_]/g, (c) => `\\${c}`)}%`

export async function listPosts({
  query = "",
  category,
  page = 1,
}: {
  query?: string
  category?: Category
  page?: number
}) {
  await connection()
  const q = query.trim()

  const conditions: SQL[] = []
  if (category) conditions.push(eq(posts.category, category))
  if (q) {
    const pattern = likePattern(q)
    conditions.push(
      or(ilike(posts.title, pattern), ilike(posts.content, pattern), ilike(posts.author, pattern))!
    )
  }
  const where = conditions.length ? and(...conditions) : undefined

  const total = await db.$count(posts, where)
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const current = Math.min(Math.max(1, page), totalPages)

  // 본문은 목록에 필요 없으므로 가져오지 않음
  const rows = await db
    .select({
      id: posts.id,
      category: posts.category,
      title: posts.title,
      author: posts.author,
      createdAt: posts.createdAt,
      updatedAt: posts.updatedAt,
      commentCount: sql<number>`(select count(*) from ${comments} where ${comments.postId} = ${posts.id})::int`,
    })
    .from(posts)
    .where(where)
    // 공지는 항상 위로, 나머지는 최신순
    .orderBy(asc(sql`case when ${posts.category} = '공지' then 0 else 1 end`), desc(posts.id))
    .limit(PAGE_SIZE)
    .offset((current - 1) * PAGE_SIZE)

  const items: PostSummary[] = rows.map((r) => ({
    ...r,
    category: r.category as Category,
    createdAt: r.createdAt.toISOString(),
    updatedAt: iso(r.updatedAt),
  }))

  return { items, total, page: current, totalPages }
}

export async function getPost(id: number): Promise<PublicPost | null> {
  await connection()
  const [post] = await db
    .select({
      id: posts.id,
      category: posts.category,
      title: posts.title,
      content: posts.content,
      author: posts.author,
      createdAt: posts.createdAt,
      updatedAt: posts.updatedAt,
    })
    .from(posts)
    .where(eq(posts.id, id))
  if (!post) return null

  const commentRows = await db
    .select({
      id: comments.id,
      author: comments.author,
      content: comments.content,
      createdAt: comments.createdAt,
    })
    .from(comments)
    .where(eq(comments.postId, id))
    .orderBy(asc(comments.id))

  return {
    ...post,
    category: post.category as Category,
    createdAt: post.createdAt.toISOString(),
    updatedAt: iso(post.updatedAt),
    comments: commentRows.map((c) => ({ ...c, createdAt: c.createdAt.toISOString() })),
  }
}
