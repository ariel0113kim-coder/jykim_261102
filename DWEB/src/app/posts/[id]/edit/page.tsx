import { notFound } from "next/navigation"
import { Suspense } from "react"
import { PostForm } from "@/components/post-form"
import { updatePost } from "@/lib/actions"
import { getPost } from "@/lib/board"

export default function EditPostPage({ params }: PageProps<"/posts/[id]/edit">) {
  return (
    <div className="grid gap-6">
      <h1 className="text-2xl font-bold tracking-tight">글 수정</h1>
      <Suspense fallback={<div className="h-96 animate-pulse rounded-xl bg-muted" />}>
        <EditForm params={params} />
      </Suspense>
    </div>
  )
}

async function EditForm({ params }: { params: PageProps<"/posts/[id]/edit">["params"] }) {
  const id = Number((await params).id)
  const post = Number.isInteger(id) ? await getPost(id) : null
  if (!post) notFound()

  return (
    <PostForm
      action={updatePost.bind(null, post.id)}
      mode="edit"
      cancelHref={`/posts/${post.id}`}
      defaultValues={{
        category: post.category,
        title: post.title,
        content: post.content,
        author: post.author,
      }}
    />
  )
}
