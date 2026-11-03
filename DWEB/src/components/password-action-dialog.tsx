"use client"

import { useActionState, useState } from "react"
import { toast } from "sonner"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { FieldError } from "@/components/field-error"
import type { FormState } from "@/lib/actions"

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>
  title: string
  description: string
  successMessage?: string
  trigger: React.ReactElement
}

// 비밀번호를 받아 삭제 같은 보호된 작업을 실행하는 확인 대화상자
export function PasswordActionDialog({ action, title, description, successMessage, trigger }: Props) {
  const [open, setOpen] = useState(false)
  const [state, formAction, pending] = useActionState(
    async (prev: FormState, formData: FormData) => {
      const result = await action(prev, formData)
      if (result.ok) {
        setOpen(false)
        if (successMessage) toast.success(successMessage)
      }
      return result
    },
    {}
  )

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger render={trigger} />
      <AlertDialogContent>
        <form action={formAction} className="grid gap-4">
          <AlertDialogHeader>
            <AlertDialogTitle>{title}</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <div className="grid gap-2">
            <Input
              name="password"
              type="password"
              placeholder="비밀번호"
              autoComplete="current-password"
              aria-label="비밀번호"
              required
              autoFocus
            />
            <FieldError message={state.error} />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel type="button">취소</AlertDialogCancel>
            <Button type="submit" variant="destructive" disabled={pending}>
              {pending ? "처리 중…" : "삭제"}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  )
}
