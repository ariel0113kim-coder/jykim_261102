import { randomBytes, scryptSync, timingSafeEqual } from "node:crypto"
import { mkdir, readFile, rename, writeFile } from "node:fs/promises"
import path from "node:path"
import { connection } from "next/server"
import type { Category } from "@/lib/categories"

export { CATEGORIES, type Category } from "@/lib/categories"

export const PAGE_SIZE = 10

export type Comment = {
  id: number
  author: string
  content: string
  passwordHash: string
  createdAt: string
}

export type Post = {
  id: number
  category: Category
  title: string
  content: string
  author: string
  passwordHash: string
  createdAt: string
  updatedAt: string | null
  comments: Comment[]
}

type Store = {
  nextPostId: number
  nextCommentId: number
  posts: Post[]
}

// 클라이언트로 보내도 되는 형태 (비밀번호 해시 제거)
export type PublicComment = Omit<Comment, "passwordHash">
export type PublicPost = Omit<Post, "passwordHash" | "comments"> & {
  comments: PublicComment[]
}
export type PostSummary = Omit<PublicPost, "content" | "comments"> & {
  commentCount: number
}

const DATA_FILE = path.join(process.cwd(), "data", "board.json")

export function hashPassword(password: string): string {
  const salt = randomBytes(16).toString("hex")
  const hash = scryptSync(password, salt, 64).toString("hex")
  return `${salt}:${hash}`
}

export function verifyPassword(password: string, stored: string): boolean {
  const [salt, hash] = stored.split(":")
  if (!salt || !hash) return false
  const expected = Buffer.from(hash, "hex")
  const actual = scryptSync(password, salt, 64)
  return expected.length === actual.length && timingSafeEqual(expected, actual)
}

function seed(): Store {
  const now = new Date().toISOString()
  return {
    nextPostId: 2,
    nextCommentId: 1,
    posts: [
      {
        id: 1,
        category: "공지",
        title: "DWEB 게시판에 오신 것을 환영합니다",
        content:
          "자유롭게 글을 남겨 주세요.\n\n글을 쓸 때 입력한 비밀번호로 글과 댓글을 수정하거나 삭제할 수 있습니다.",
        author: "관리자",
        passwordHash: hashPassword("admin1234"),
        createdAt: now,
        updatedAt: null,
        comments: [],
      },
    ],
  }
}

async function readStore(): Promise<Store> {
  try {
    return JSON.parse(await readFile(DATA_FILE, "utf8")) as Store
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error
    const initial = seed()
    await writeStore(initial)
    return initial
  }
}

async function writeStore(store: Store) {
  await mkdir(path.dirname(DATA_FILE), { recursive: true })
  const tmp = `${DATA_FILE}.tmp`
  await writeFile(tmp, JSON.stringify(store, null, 2), "utf8")
  await rename(tmp, DATA_FILE)
}

// 동시에 들어온 쓰기 요청이 서로 덮어쓰지 않도록 순서대로 처리
let queue: Promise<unknown> = Promise.resolve()
export function mutate<T>(fn: (store: Store) => T | Promise<T>): Promise<T> {
  const run = queue.then(async () => {
    const store = await readStore()
    const result = await fn(store)
    await writeStore(store)
    return result
  })
  queue = run.catch(() => {})
  return run
}

function toSummary(post: Post): PostSummary {
  return {
    id: post.id,
    category: post.category,
    title: post.title,
    author: post.author,
    createdAt: post.createdAt,
    updatedAt: post.updatedAt,
    commentCount: post.comments.length,
  }
}

function toPublic(post: Post): PublicPost {
  return {
    id: post.id,
    category: post.category,
    title: post.title,
    author: post.author,
    createdAt: post.createdAt,
    updatedAt: post.updatedAt,
    content: post.content,
    comments: post.comments.map((c) => ({
      id: c.id,
      author: c.author,
      content: c.content,
      createdAt: c.createdAt,
    })),
  }
}

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
  const { posts } = await readStore()
  const q = query.trim().toLowerCase()

  const filtered = posts
    .filter((p) => !category || p.category === category)
    .filter(
      (p) =>
        !q ||
        p.title.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q)
    )
    // 공지는 항상 위로, 나머지는 최신순
    .sort((a, b) => {
      const notice = Number(b.category === "공지") - Number(a.category === "공지")
      return notice || b.id - a.id
    })

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const current = Math.min(Math.max(1, page), totalPages)
  const items = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE).map(toSummary)

  return { items, total: filtered.length, page: current, totalPages }
}

export async function getPost(id: number): Promise<PublicPost | null> {
  await connection()
  const { posts } = await readStore()
  const post = posts.find((p) => p.id === id)
  return post ? toPublic(post) : null
}
