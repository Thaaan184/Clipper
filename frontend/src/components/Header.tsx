import React, { useEffect, useRef } from "react"
import { Link, useLocation } from "react-router-dom"

export default function Header() {
  const loc = useLocation()
  const tcRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let frame = 0
    const interval = setInterval(() => {
      frame++
      const s = Math.floor(frame / 24)
      const h = String(Math.floor(s / 3600)).padStart(2, "0")
      const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0")
      const sec = String(s % 60).padStart(2, "0")
      const f = String(frame % 24).padStart(2, "0")
      if (tcRef.current) {
        tcRef.current.textContent = `${h}:${m}:${sec}:${f}`
      }
    }, 42)
    return () => clearInterval(interval)
  }, [])

  return (
    <header className="site-header">
      <Link to="/" className="brand" aria-label="ClipForge">
        <span className="brand-mark" aria-hidden="true">
          <span />
        </span>
        <span>CLIPFORGE</span>
      </Link>

      <nav className="header-nav">
        <Link to="/" className={`nav-tab ${loc.pathname === "/" ? "active" : ""}`}>
          BERANDA
        </Link>
        <Link
          to="/#proyek"
          className="nav-tab"
          onClick={() => {
            if (loc.pathname === "/") {
              const el = document.getElementById("proyek")
              if (el) el.scrollIntoView({ behavior: "smooth" })
            }
          }}
        >
          PROYEK
        </Link>
      </nav>

      <div className="header-tc" ref={tcRef}>
        00:00:00:00
      </div>
    </header>
  )
}
