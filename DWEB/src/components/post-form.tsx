"use client"

import Link from "next/link"
import { useActionState, useId } from "react"
import { Button, buttonVariants } from "@/components/ui/button"
import { Card, CardContent, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { FieldError } from "@/components/field-error"
import { CATEGORIES, type Category } from "@/lib/categories"
import type { FormState } from "@/lib/actions"

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>
  mode: "create" | "edit"
  defaultValues?: { category: Category; title: string; content: string; author: string }
  cancelHref: string
}

export function PostForm({ action, mode, defaultValues, cancelHref }: Props) {
  const [state, formAction, pending] = useActionState(action, {})
  const errors = state.fieldErrors ?? {}
  const values = { ...defaultValues, ...state.values }
  // 이전 페이지가 숨겨진 채 DOM에 남을 수 있어 id가 겹치지 않게 함
  const uid = useId()
  const id = (name: string) => `${uid}-${name}`

  return (
    <form action={formAction}>
      <Card>
        <CardContent className="grid gap-5">
          <div className="grid gap-4 sm:grid-cols-[160px_1fr]">
            <div className="grid gap-2">
              <Label htmlFor={id("category")}>분류</Label>
              <Select name="category" defaultValue={values.category ?? "자유"}>
                <SelectTrigger id={id("category")} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FieldError message={errors.category} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={id("title")}>제목</Label>
              <Input
                id={id("title")}
                name="title"
                maxLength={100}
                defaultValue={values.title}
                aria-invalid={!!errors.title}
                required
              />
              <FieldError message={errors.title} />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor={id("content")}>내용</Label>
            <Textarea
              id={id("content")}
              name="content"
              rows={12}
              maxLength={5000}
              defaultValue={values.content}
              aria-invalid={!!errors.content}
              required
            />
            <FieldError message={errors.content} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor={id("author")}>작성자</Label>
              <Input
                id={id("author")}
                name="author"
                maxLength={20}
                defaultValue={values.author}
                disabled={mode === "edit"}
                aria-invalid={!!errors.author}
                required
              />
              <FieldError message={errors.author} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor={id("password")}>
                비밀번호 {mode === "edit" ? "확인" : <span className="text-muted-foreground">(수정·삭제 시 필요)</span>}
              </Label>
              <Input
                id={id("password")}
                name="password"
                type="password"
                minLength={4}
                maxLength={20}
                autoComplete={mode === "edit" ? "current-password" : "new-password"}
                aria-invalid={!!errors.password}
                required
              />
              <FieldError message={errors.password} />
            </div>
          </div>

          <FieldError message={state.error} />
        </CardContent>
        <CardFooter className="justify-end gap-2">
          <Link href={cancelHref} className={buttonVariants({ variant: "outline" })}>
            취소
          </Link>
          <Button type="submit" disabled={pending}>
            {pending ? "저장 중…" : mode === "edit" ? "수정하기" : "등록하기"}
          </Button>
        </CardFooter>
      </Card>
    </form>
  )
}
