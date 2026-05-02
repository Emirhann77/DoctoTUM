import { redirect } from "next/navigation";

/** If this runs, rewrites/middleware did not map `/` to static `index.html` (see `next.config.ts`, `middleware.ts`). */
export default function Home() {
  redirect("/index.html");
}
