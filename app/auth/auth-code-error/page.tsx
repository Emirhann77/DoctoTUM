import Link from "next/link";

export default function AuthCodeErrorPage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "2rem",
        gap: "1rem",
        textAlign: "center",
      }}
    >
      <h1 style={{ margin: 0 }}>Sign-in could not be completed</h1>
      <p style={{ margin: 0, color: "var(--muted)", maxWidth: 420 }}>
        The auth callback did not receive a valid code. Check redirect URLs in Supabase
        Auth settings and try again.
      </p>
      <Link href="/">Back home</Link>
    </main>
  );
}
