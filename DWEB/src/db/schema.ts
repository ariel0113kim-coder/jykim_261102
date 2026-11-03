import { index, integer, pgTable, serial, text, timestamp, varchar } from "drizzle-orm/pg-core"

export const posts = pgTable(
  "posts",
  {
    id: serial("id").primaryKey(),
    category: varchar("category", { length: 10 }).notNull(),
    title: varchar("title", { length: 100 }).notNull(),
    content: text("content").notNull(),
    author: varchar("author", { length: 20 }).notNull(),
    passwordHash: text("password_hash").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }),
  },
  (t) => [index("posts_category_idx").on(t.category)]
)

export const comments = pgTable(
  "comments",
  {
    id: serial("id").primaryKey(),
    postId: integer("post_id")
      .notNull()
      .references(() => posts.id, { onDelete: "cascade" }),
    author: varchar("author", { length: 20 }).notNull(),
    content: text("content").notNull(),
    passwordHash: text("password_hash").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index("comments_post_id_idx").on(t.postId)]
)
