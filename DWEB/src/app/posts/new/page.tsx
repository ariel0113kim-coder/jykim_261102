import type { Metadata } from "next"
import { PostForm } from "@/components/post-form"
import { createPost } from "@/lib/actions"

export const metadata: Metadata = { title: "글쓰기" }

export default function NewPostPage() {
  return (
    <div className="grid gap-6">
      <h1 className="text-2xl font-bold tracking-tight">글쓰기</h1>
      <PostForm action={createPost} mode="create" cancelHref="/" />
    </div>
  )
}
