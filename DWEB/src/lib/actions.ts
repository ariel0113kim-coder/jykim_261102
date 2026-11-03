"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"
import { and, eq } from "drizzle-orm"
import { db } from "@/db"
import { comments, posts } from "@/db/schema"
import { CATEGORIES, type Category } from "@/lib/categories"
import { hashPassword, verifyPassword } from "@/lib/password"

export type FormState = {
  error?: string
  fieldErrors?: Partial<Record<string, string>>
  // 오류 시 폼이 초기화되어도 입력값을 되살리기 위한 값 (비밀번호 제외)
  values?: Record<string, string>
  ok?: boolean
}

const str = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim()

async function postPasswordHash(id: number) {
  const [row] = await db.select({ passwordHash: posts.passwordHash }).from(posts).where(eq(posts.id, id))
  return row?.passwordHash
}

function validatePostFields(fd: FormData, { requireAuthorFields = true } = {}) {
  const fieldErrors: Record<string, string> = {}
  const category = str(fd, "category") as Category
  const title = str(fd, "title")
  const content = str(fd, "content")
  const author = str(fd, "author")
  const password = String(fd.get("password") ?? "")

  if (!CATEGORIES.includes(category)) fieldErrors.category = "분류를 선택해 주세요."
  if (!title) fieldErrors.title = "제목을 입력해 주세요."
  else if (title.length > 100) fieldErrors.title = "제목은 100자 이하로 입력해 주세요."
  if (!content) fieldErrors.content = "내용을 입력해 주세요."
  else if (content.length > 5000) fieldErrors.content = "내용은 5000자 이하로 입력해 주세요."
  if (requireAuthorFields) {
    if (!author) fieldErrors.author = "작성자를 입력해 주세요."
    else if (author.length > 20) fieldErrors.author = "작성자는 20자 이하로 입력해 주세요."
  }
  if (password.length < 4 || password.length > 20)
    fieldErrors.password = "비밀번호는 4~20자로 입력해 주세요."

  return {
    fieldErrors,
    values: { category, title, content, author, password },
    echo: { category, title, content, author },
  }
}

export async function createPost(_prev: FormState, fd: FormData): Promise<FormState> {
  const { fieldErrors, values, echo } = validatePostFields(fd)
  if (Object.keys(fieldErrors).length) return { fieldErrors, values: echo }

  const [{ id }] = await db
    .insert(posts)
    .values({
      category: values.category,
      title: values.title,
      content: values.content,
      author: values.author,
      passwordHash: hashPassword(values.password),
    })
    .returning({ id: posts.id })

  revalidatePath("/")
  redirect(`/posts/${id}`)
}

export async function updatePost(
  id: number,
  _prev: FormState,
  fd: FormData
): Promise<FormState> {
  const { fieldErrors, values, echo } = validatePostFields(fd, { requireAuthorFields: false })
  if (Object.keys(fieldErrors).length) return { fieldErrors, values: echo }

  const hash = await postPasswordHash(id)
  if (!hash) return { error: "게시글을 찾을 수 없습니다." }
  if (!verifyPassword(values.password, hash))
    return { fieldErrors: { password: "비밀번호가 일치하지 않습니다." }, values: echo }

  await db
    .update(posts)
    .set({
      category: values.category,
      title: values.title,
      content: values.content,
      updatedAt: new Date(),
    })
    .where(eq(posts.id, id))

  revalidatePath("/")
  revalidatePath(`/posts/${id}`)
  redirect(`/posts/${id}`)
}

export async function deletePost(
  id: number,
  _prev: FormState,
  fd: FormData
): Promise<FormState> {
  const password = String(fd.get("password") ?? "")
  const hash = await postPasswordHash(id)
  if (!hash) return { error: "게시글을 찾을 수 없습니다." }
  if (!verifyPassword(password, hash)) return { error: "비밀번호가 일치하지 않습니다." }

  // 댓글은 외래 키의 ON DELETE CASCADE로 함께 삭제됨
  await db.delete(posts).where(eq(posts.id, id))

  revalidatePath("/")
  redirect("/")
}

export async function addComment(
  postId: number,
  _prev: FormState,
  fd: FormData
): Promise<FormState> {
  const author = str(fd, "author")
  const content = str(fd, "content")
  const password = String(fd.get("password") ?? "")
  const fieldErrors: Record<string, string> = {}
  if (!author || author.length > 20) fieldErrors.author = "작성자는 1~20자로 입력해 주세요."
  if (!content || content.length > 1000) fieldErrors.content = "댓글은 1~1000자로 입력해 주세요."
  if (password.length < 4 || password.length > 20)
    fieldErrors.password = "비밀번호는 4~20자로 입력해 주세요."
  if (Object.keys(fieldErrors).length) return { fieldErrors, values: { author, content } }

  if (!(await postPasswordHash(postId))) return { error: "게시글을 찾을 수 없습니다." }
  await db.insert(comments).values({
    postId,
    author,
    content,
    passwordHash: hashPassword(password),
  })

  revalidatePath(`/posts/${postId}`)
  revalidatePath("/")
  return { ok: true }
}

export async function deleteComment(
  postId: number,
  commentId: number,
  _prev: FormState,
  fd: FormData
): Promise<FormState> {
  const password = String(fd.get("password") ?? "")
  const where = and(eq(comments.id, commentId), eq(comments.postId, postId))
  const [comment] = await db.select({ passwordHash: comments.passwordHash }).from(comments).where(where)
  if (!comment) return { error: "댓글을 찾을 수 없습니다." }
  if (!verifyPassword(password, comment.passwordHash)) return { error: "비밀번호가 일치하지 않습니다." }

  await db.delete(comments).where(where)

  revalidatePath(`/posts/${postId}`)
  revalidatePath("/")
  return { ok: true }
}
