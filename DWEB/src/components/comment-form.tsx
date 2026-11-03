"use client"

import { useActionState, useEffect } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { FieldError } from "@/components/field-error"
import type { FormState } from "@/lib/actions"

export function CommentForm({
  action,
}: {
  action: (state: FormState, formData: FormData) => Promise<FormState>
}) {
  const [state, formAction, pending] = useActionState(action, {})
  const errors = state.fieldErrors ?? {}

  useEffect(() => {
    if (state.ok) toast.success("댓글을 등록했어요")
  }, [state])

  return (
    <form action={formAction} className="grid gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="grid gap-1">
          <Input name="author" defaultValue={state.values?.author} placeholder="작성자" maxLength={20} aria-label="작성자" required />
          <FieldError message={errors.author} />
        </div>
        <div className="grid gap-1">
          <Input
            name="password"
            type="password"
            placeholder="비밀번호 (삭제 시 필요)"
            minLength={4}
            maxLength={20}
            autoComplete="new-password"
            aria-label="비밀번호"
            required
          />
          <FieldError message={errors.password} />
        </div>
      </div>
      <div className="grid gap-1">
        <Textarea
          defaultValue={state.values?.content}
          name="content"
          placeholder="댓글을 입력하세요"
          rows={3}
          maxLength={1000}
          aria-label="댓글 내용"
          required
        />
        <FieldError message={errors.content ?? state.error} />
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={pending}>
          {pending ? "등록 중…" : "댓글 등록"}
        </Button>
      </div>
    </form>
  )
}
