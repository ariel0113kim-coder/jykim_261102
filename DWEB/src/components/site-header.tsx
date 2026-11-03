import Link from "next/link"
import { MessagesSquareIcon, PencilIcon } from "lucide-react"
import { buttonVariants } from "@/components/ui/button"
import { ThemeToggle } from "@/components/theme-toggle"

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-4xl items-center gap-2 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <MessagesSquareIcon className="size-5 text-primary" />
          DWEB 게시판
        </Link>
        <div className="ml-auto flex items-center gap-1">
          <Link href="/posts/new" className={buttonVariants({ size: "sm" })}>
            <PencilIcon />
            글쓰기
          </Link>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
