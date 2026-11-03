"use server"

import { revalidatePath } from "next/cache"
import { redirect } from "next/navigation"
import {
  CATEGORIES,
  type Category,
  hashPassword,
  mutate,
  verifyPassword,
} from "@/lib/board"

export type FormState = {
  error?: string
  fieldErrors?: Partial<Record<string, string>>
  // 오류 시 폼이 초기화되어도 입력값을 되살리기 위한 값 (비밀번호 제외)
  values?: Record<string, string>
  ok?: boolean
}

const str = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim()

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

  const id = await mutate((store) => {
    const id = store.nextPostId++
    store.posts.push({
      id,
      category: values.category,
      title: values.title,
      content: values.content,
      author: values.author,
      passwordHash: hashPassword(values.password),
      createdAt: new Date().toISOString(),
      updatedAt: null,
      comments: [],
    })
    return id
  })

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

  const result = await mutate((store) => {
    const post = store.posts.find((p) => p.id === id)
    if (!post) return "not-found" as const
    if (!verifyPassword(values.password, post.passwordHash)) return "forbidden" as const
    post.category = values.category
    post.title = values.title
    post.content = values.content
    post.updatedAt = new Date().toISOString()
    return "ok" as const
  })

  if (result === "not-found") return { error: "게시글을 찾을 수 없습니다." }
  if (result === "forbidden")
    return { fieldErrors: { password: "비밀번호가 일치하지 않습니다." }, values: echo }

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
  const result = await mutate((store) => {
    const index = store.posts.findIndex((p) => p.id === id)
    if (index < 0) return "not-found" as const
    if (!verifyPassword(password, store.posts[index].passwordHash)) return "forbidden" as const
    store.posts.splice(index, 1)
    return "ok" as const
  })

  if (result === "not-found") return { error: "게시글을 찾을 수 없습니다." }
  if (result === "forbidden") return { error: "비밀번호가 일치하지 않습니다." }

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

  const ok = await mutate((store) => {
    const post = store.posts.find((p) => p.id === postId)
    if (!post) return false
    post.comments.push({
      id: store.nextCommentId++,
      author,
      content,
      passwordHash: hashPassword(password),
      createdAt: new Date().toISOString(),
    })
    return true
  })
  if (!ok) return { error: "게시글을 찾을 수 없습니다." }

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
  const result = await mutate((store) => {
    const post = store.posts.find((p) => p.id === postId)
    const index = post?.comments.findIndex((c) => c.id === commentId) ?? -1
    if (!post || index < 0) return "not-found" as const
    if (!verifyPassword(password, post.comments[index].passwordHash)) return "forbidden" as const
    post.comments.splice(index, 1)
    return "ok" as const
  })

  if (result === "not-found") return { error: "댓글을 찾을 수 없습니다." }
  if (result === "forbidden") return { error: "비밀번호가 일치하지 않습니다." }

  revalidatePath(`/posts/${postId}`)
  revalidatePath("/")
  return { ok: true }
}
