// Shared Tailwind config injected into every page via inline script
window.tailwind && (tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "on-secondary-container": "#007354",
        "on-primary": "#ffffff",
        "on-tertiary": "#ffffff",
        "secondary-fixed-dim": "#62dcaf",
        "background": "#f7f9fb",
        "on-primary-fixed-variant": "#00419c",
        "inverse-on-surface": "#eff1f3",
        "tertiary": "#2724b8",
        "on-error-container": "#93000a",
        "on-primary-fixed": "#001945",
        "surface-container-high": "#e6e8ea",
        "primary-fixed": "#d9e2ff",
        "on-tertiary-fixed": "#07006c",
        "outline": "#737784",
        "on-primary-container": "#bcceff",
        "error": "#ba1a1a",
        "surface-container-low": "#f2f4f6",
        "surface-tint": "#1d59c1",
        "tertiary-fixed": "#e1e0ff",
        "on-surface-variant": "#434653",
        "inverse-surface": "#2d3133",
        "error-container": "#ffdad6",
        "on-surface": "#191c1e",
        "secondary": "#006c4f",
        "on-background": "#191c1e",
        "secondary-fixed": "#80f9ca",
        "on-tertiary-fixed-variant": "#2f2ebe",
        "on-secondary": "#ffffff",
        "surface-dim": "#d8dadc",
        "on-secondary-fixed-variant": "#00513b",
        "surface-bright": "#f7f9fb",
        "on-tertiary-container": "#c9caff",
        "on-secondary-fixed": "#002116",
        "tertiary-fixed-dim": "#c0c1ff",
        "surface": "#f7f9fb",
        "primary-container": "#0f52ba",
        "outline-variant": "#c3c6d5",
        "primary": "#003c90",
        "surface-container": "#eceef0",
        "tertiary-container": "#4243cf",
        "on-error": "#ffffff",
        "primary-fixed-dim": "#b0c6ff",
        "surface-variant": "#e0e3e5",
        "secondary-container": "#80f9ca",
        "inverse-primary": "#b0c6ff",
        "surface-container-highest": "#e0e3e5",
        "surface-container-lowest": "#ffffff"
      },
      borderRadius: { DEFAULT: "0.25rem", lg: "0.5rem", xl: "0.75rem", full: "9999px" },
      spacing: { lg: "24px", xs: "8px", xl: "32px", sm: "12px", gutter: "16px", base: "4px", margin: "20px", md: "16px" },
      fontFamily: {
        "body-lg": ["Public Sans"], "body-md": ["Public Sans"], "h3": ["Manrope"],
        "body-sm": ["Public Sans"], "h2": ["Manrope"], "label-caps": ["Public Sans"],
        "h1": ["Manrope"], "button": ["Public Sans"]
      },
      fontSize: {
        "body-lg": ["18px", { lineHeight: "28px", fontWeight: "400" }],
        "body-md": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "h3": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "h2": ["24px", { lineHeight: "32px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "label-caps": ["12px", { lineHeight: "16px", letterSpacing: "0.05em", fontWeight: "700" }],
        "h1": ["30px", { lineHeight: "38px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "button": ["16px", { lineHeight: "20px", fontWeight: "600" }]
      }
    }
  }
});
