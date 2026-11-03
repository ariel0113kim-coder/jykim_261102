export const CATEGORIES = ["공지", "자유", "질문", "정보"] as const
export type Category = (typeof CATEGORIES)[number]
