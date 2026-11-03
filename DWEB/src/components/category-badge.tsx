import { Badge } from "@/components/ui/badge"
import type { Category } from "@/lib/board"

const variants: Record<Category, React.ComponentProps<typeof Badge>["variant"]> = {
  공지: "destructive",
  자유: "secondary",
  질문: "outline",
  정보: "default",
}

export function CategoryBadge({ category }: { category: Category }) {
  return <Badge variant={variants[category]}>{category}</Badge>
}
