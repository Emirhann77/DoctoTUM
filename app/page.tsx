import { createClient } from "@/lib/supabase/server";

function envConfigured() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  return Boolean(
    url &&
      key &&
      !url.includes("YOUR_PROJECT_REF") &&
      key !== "your_anon_public_key_here",
  );
}

export default async function Home() {
  const configured = envConfigured();
  let supabaseStatus: "skipped" | "ok" | "error" = "skipped";
  let supabaseDetail = "Add keys to .env.local to verify the connection.";

  if (configured) {
    try {
      const supabase = await createClient();
      const {
        data: { user },
        error,
      } = await supabase.auth.getUser();
      if (error) {
        const msg = error.message?.toLowerCase() ?? "";
        const noSessionYet =
          msg.includes("session missing") || error.name === "AuthSessionMissingError";
        if (noSessionYet) {
          supabaseStatus = "ok";
          supabaseDetail =
            "Supabase reachable. No login session yet (normal until you add sign-in).";
        } else {
          supabaseStatus = "error";
          supabaseDetail = error.message;
        }
      } else {
        supabaseStatus = "ok";
        supabaseDetail = user
          ? `Session OK — signed in as ${user.email ?? user.id}.`
          : "Supabase reachable; no user in this request (expected before login).";
      }
    } catch (e) {
      supabaseStatus = "error";
      supabaseDetail = e instanceof Error ? e.message : "Unknown error";
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "1.25rem",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 520 }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, margin: "0 0 0.5rem" }}>
          DoctoTUM
        </h1>
        <p style={{ margin: 0, color: "var(--muted)" }}>
          Online doctoral assistant — Supabase is wired for Next.js (browser + server + middleware).
        </p>
      </div>

      <section
        style={{
          width: "100%",
          maxWidth: 520,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: 12,
          padding: "1.25rem 1.5rem",
        }}
      >
        <h2 style={{ fontSize: "1rem", margin: "0 0 0.75rem", fontWeight: 600 }}>
          Configuration
        </h2>
        <ul style={{ margin: 0, paddingLeft: "1.25rem", color: "var(--muted)" }}>
          <li>
            Copy <code>.env.example</code> → <code>.env.local</code>
          </li>
          <li>
            Set <code>NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
            <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code> from the Supabase dashboard
          </li>
        </ul>
        <p style={{ margin: "1rem 0 0", fontSize: "0.9rem" }}>
          <strong>Env:</strong>{" "}
          {configured ? (
            <span style={{ color: "var(--accent)" }}>looks configured</span>
          ) : (
            <span style={{ color: "#f0ad4e" }}>waiting for real keys in .env.local</span>
          )}
        </p>
        <p style={{ margin: "0.5rem 0 0", fontSize: "0.9rem" }}>
          <strong>Supabase check:</strong>{" "}
          {supabaseStatus === "ok" && (
            <span style={{ color: "var(--accent)" }}>OK — {supabaseDetail}</span>
          )}
          {supabaseStatus === "error" && (
            <span style={{ color: "#f85149" }}>Error — {supabaseDetail}</span>
          )}
          {supabaseStatus === "skipped" && (
            <span style={{ color: "var(--muted)" }}>{supabaseDetail}</span>
          )}
        </p>
      </section>
    </main>
  );
}
