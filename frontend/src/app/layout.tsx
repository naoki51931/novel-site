import type { Metadata } from "next";
import Script from "next/script";
import "../styles.css";

const siteTitle = "小説投稿サイトLexis（レクシー/レクシス）";
const siteDescription =
  "小説投稿サイトLexis（レクシー/レクシス）。誰でも小説を読めて、作品を投稿できます。恋愛・ファンタジー・SF・ホラーなど幅広いジャンルの作品を公開中。";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_ORIGIN || "https://shosetsu-toukou-site.org"),
  title: {
    default: `${siteTitle}| 誰でも小説が読めて投稿できる無料サイト`,
    template: `%s｜${siteTitle}`,
  },
  description: siteDescription,
  keywords: [
    "小説",
    "小説投稿",
    "小説サイト",
    "web小説",
    "無料小説",
    "執筆",
    "読書",
    "AI小説",
    "AI小説生成",
    "小説生成AI",
    "R18小説",
    "R18小説生成",
    "官能小説生成",
    "AIチャット",
    "ライトノベル",
    "Lexis",
    "レクシー",
    "レクシス",
  ],
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
    },
  },
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/favicon-48x48.png", type: "image/png", sizes: "48x48" },
      { url: "/favicon-96x96.png", type: "image/png", sizes: "96x96" },
      { url: "/favicon-192x192.png", type: "image/png", sizes: "192x192" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
  },
  openGraph: {
    title: siteTitle,
    description: "誰でも小説が読めて投稿できる小説投稿サイトLexis（レクシー/レクシス）。",
    type: "website",
    siteName: siteTitle,
    images: [
      {
        url: "/ogp.png",
        width: 1200,
        height: 630,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: siteTitle,
    description: "誰でも小説が読めて投稿できる小説投稿サイトLexis（レクシー/レクシス）。",
    images: ["/ogp.png"],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <noscript>
          <iframe
            src="https://www.googletagmanager.com/ns.html?id=GTM-PLK23FZR"
            height="0"
            width="0"
            style={{ display: "none", visibility: "hidden" }}
          />
        </noscript>
        {children}
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-FN5KC9TFR2"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-FN5KC9TFR2');
            gtag('config', 'AW-781963249');
          `}
        </Script>
        <Script id="google-tag-manager" strategy="afterInteractive">
          {`
            (function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
            new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
            j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
            'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
            })(window,document,'script','dataLayer','GTM-PLK23FZR');
          `}
        </Script>
      </body>
    </html>
  );
}
