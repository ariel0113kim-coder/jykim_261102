import Link from "next/link"
import { Suspense } from "react"
import { MessageSquareIcon, SearchIcon } from "lucide-react"
import { CategoryBadge } from "@/components/category-badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { CATEGORIES, type Category, listPosts } from "@/lib/board"
import { formatDate } from "@/lib/format"
import { cn } from "@/lib/utils"

type Search = { q: string; category?: Category; page: number }

function buildHref({ q, category, page }: Partial<Search>) {
  const params = new URLSearchParams()
  if (q) params.set("q", q)
  if (category) params.set("category", category)
  if (page && page > 1) params.set("page", String(page))
  const qs = params.toString()
  return qs ? `/?${qs}` : "/"
}

export default function HomePage({ searchParams }: PageProps<"/">) {
  return (
    <div className="grid gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">게시판</h1>
        <p className="text-sm text-muted-foreground">자유롭게 이야기를 나눠 보세요.</p>
      </div>
      <Suspense fallback={<BoardSkeleton />}>
        <Board searchParams={searchParams} />
      </Suspense>
    </div>
  )
}

async function Board({ searchParams }: { searchParams: PageProps<"/">["searchParams"] }) {
  const sp = await searchParams
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) ?? ""
  const q = one(sp.q)
  const rawCategory = one(sp.category)
  const category = CATEGORIES.find((c) => c === rawCategory)
  const page = Number.parseInt(one(sp.page), 10) || 1

  const result = await listPosts({ query: q, category, page })

  return (
    <div className="grid gap-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <nav className="flex flex-wrap gap-1" aria-label="분류">
          {[undefined, ...CATEGORIES].map((c) => (
            <Link
              key={c ?? "all"}
              href={buildHref({ q, category: c })}
              className={buttonVariants({ variant: c === category ? "default" : "ghost", size: "sm" })}
              aria-current={c === category ? "page" : undefined}
            >
              {c ?? "전체"}
            </Link>
          ))}
        </nav>
        <form action="/" className="flex gap-2" role="search">
          {category && <input type="hidden" name="category" value={category} />}
          <Input
            name="q"
            defaultValue={q}
            placeholder="제목, 내용, 작성자 검색"
            aria-label="검색어"
            className="sm:w-60"
          />
          <Button type="submit" variant="outline" size="icon" aria-label="검색">
            <SearchIcon />
          </Button>
        </form>
      </div>

      <Card className="py-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="hidden w-16 text-center sm:table-cell">번호</TableHead>
              <TableHead>제목</TableHead>
              <TableHead className="hidden w-28 sm:table-cell">작성자</TableHead>
              <TableHead className="w-28 text-right">작성일</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {result.items.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="h-32 text-center text-muted-foreground">
                  {q || category ? "조건에 맞는 게시글이 없어요." : "아직 게시글이 없어요. 첫 글을 남겨 보세요!"}
                </TableCell>
              </TableRow>
            ) : (
              result.items.map((post) => (
                <TableRow key={post.id} className={cn(post.category === "공지" && "bg-muted/40")}>
                  <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                    {post.id}
                  </TableCell>
                  <TableCell className="max-w-0">
                    <Link href={`/posts/${post.id}`} className="flex items-center gap-2 hover:underline">
                      <CategoryBadge category={post.category} />
                      <span className="truncate font-medium">{post.title}</span>
                      {post.commentCount > 0 && (
                        <span className="flex shrink-0 items-center gap-0.5 text-xs text-primary">
                          <MessageSquareIcon className="size-3" />
                          {post.commentCount}
                        </span>
                      )}
                    </Link>
                    <span className="text-xs text-muted-foreground sm:hidden">{post.author}</span>
                  </TableCell>
                  <TableCell className="hidden truncate sm:table-cell">{post.author}</TableCell>
                  <TableCell className="text-right text-muted-foreground">
                    {formatDate(post.createdAt)}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>총 {result.total}개</span>
        {result.totalPages > 1 && (
          <nav className="flex gap-1" aria-label="페이지">
            {Array.from({ length: result.totalPages }, (_, i) => i + 1).map((p) => (
              <Link
                key={p}
                href={buildHref({ q, category, page: p })}
                className={buttonVariants({ variant: p === result.page ? "default" : "outline", size: "icon-sm" })}
                aria-current={p === result.page ? "page" : undefined}
              >
                {p}
              </Link>
            ))}
          </nav>
        )}
      </div>
    </div>
  )
}

function BoardSkeleton() {
  return (
    <div className="grid gap-4">
      <div className="h-8 w-full animate-pulse rounded-lg bg-muted" />
      <div className="h-80 w-full animate-pulse rounded-xl bg-muted" />
    </div>
  )
}
