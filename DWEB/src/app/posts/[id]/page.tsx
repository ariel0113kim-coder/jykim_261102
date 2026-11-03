import Link from "next/link"
import { notFound } from "next/navigation"
import { Suspense } from "react"
import { ArrowLeftIcon, PencilIcon, Trash2Icon } from "lucide-react"
import { CategoryBadge } from "@/components/category-badge"
import { CommentForm } from "@/components/comment-form"
import { PasswordActionDialog } from "@/components/password-action-dialog"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { addComment, deleteComment, deletePost } from "@/lib/actions"
import { getPost } from "@/lib/board"
import { formatDateTime } from "@/lib/format"

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <div className="grid gap-6">
      <Link href="/" className={buttonVariants({ variant: "ghost", size: "sm", className: "w-fit" })}>
        <ArrowLeftIcon />
        목록으로
      </Link>
      <Suspense fallback={<div className="h-96 animate-pulse rounded-xl bg-muted" />}>
        <PostDetail params={params} />
      </Suspense>
    </div>
  )
}

async function PostDetail({ params }: { params: PageProps<"/posts/[id]">["params"] }) {
  const id = Number((await params).id)
  const post = Number.isInteger(id) ? await getPost(id) : null
  if (!post) notFound()

  return (
    <>
      <Card>
        <CardHeader className="gap-3">
          <div className="flex items-center gap-2">
            <CategoryBadge category={post.category} />
            <span className="text-xs text-muted-foreground">#{post.id}</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight break-words">{post.title}</h1>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="font-medium text-foreground">{post.author}</span>
            <span>{formatDateTime(post.createdAt)}</span>
            {post.updatedAt && <span>(수정됨 {formatDateTime(post.updatedAt)})</span>}
          </div>
        </CardHeader>
        <Separator />
        <CardContent>
          <div className="min-h-32 leading-relaxed break-words whitespace-pre-wrap">{post.content}</div>
          <div className="mt-8 flex justify-end gap-2">
            <Link href={`/posts/${post.id}/edit`} className={buttonVariants({ variant: "outline", size: "sm" })}>
              <PencilIcon />
              수정
            </Link>
            <PasswordActionDialog
              action={deletePost.bind(null, post.id)}
              title="게시글을 삭제할까요?"
              description="삭제한 글과 댓글은 되돌릴 수 없어요. 글을 쓸 때 입력한 비밀번호를 입력해 주세요."
              trigger={
                <Button variant="destructive" size="sm">
                  <Trash2Icon />
                  삭제
                </Button>
              }
            />
          </div>
        </CardContent>
      </Card>

      <section className="grid gap-4" aria-labelledby="comments-title">
        <h2 id="comments-title" className="text-lg font-semibold">
          댓글 <span className="text-primary">{post.comments.length}</span>
        </h2>

        {post.comments.length > 0 && (
          <ul className="grid gap-3">
            {post.comments.map((c) => (
              <li key={c.id} className="rounded-xl border bg-card p-4">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{c.author}</span>
                  <span className="text-xs text-muted-foreground">{formatDateTime(c.createdAt)}</span>
                  <div className="ml-auto">
                    <PasswordActionDialog
                      action={deleteComment.bind(null, post.id, c.id)}
                      title="댓글을 삭제할까요?"
                      description="댓글을 쓸 때 입력한 비밀번호를 입력해 주세요."
                      successMessage="댓글을 삭제했어요"
                      trigger={
                        <Button variant="ghost" size="icon-xs" aria-label="댓글 삭제">
                          <Trash2Icon />
                        </Button>
                      }
                    />
                  </div>
                </div>
                <p className="mt-2 text-sm break-words whitespace-pre-wrap">{c.content}</p>
              </li>
            ))}
          </ul>
        )}

        <Card>
          <CardContent>
            <CommentForm action={addComment.bind(null, post.id)} />
          </CardContent>
        </Card>
      </section>
    </>
  )
}
