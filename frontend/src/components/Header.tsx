import React, { useState, useEffect } from "react"
import { Link, useLocation } from "react-router-dom"

export default function Header() {
  const loc = useLocation()
  const [tc, setTc] = useState("00:00:00:00")

  useEffect(() => {
    let frame = 0
    const interval = setInterval(() => {
      frame++
      const s = Math.floor(frame / 24)
      const h = String(Math.floor(s / 3600)).padStart(2, "0")
      const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0")
      const sec = String(s % 60).padStart(2, "0")
      const f = String(frame % 24).padStart(2, "0")
      setTc(`${h}:${m}:${sec}:${f}`)
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
        <a href="#proyek" className="nav-tab">
          PROYEK
        </a>
      </nav>

      <div className="header-tc">{tc}</div>
    </header>
  )
}
