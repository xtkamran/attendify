import { useEffect, useState } from 'react'
import axios from 'axios'
import {
  LayoutDashboard, Users, CalendarCheck, ChartNoAxesCombined,
  Settings, Search, Bell, Clock3, UserCheck, UserX,
  TrendingUp, ChevronDown, Menu
} from 'lucide-react'

const API_URL = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8002').replace(/\/$/, '')
const TOKEN_KEY = 'attendify_access_token'

const navigation = [
  { label: 'Dashboard', icon: LayoutDashboard },
  { label: 'Employees', icon: Users },
  { label: 'Attendance', icon: CalendarCheck },
  { label: 'Analytics', icon: ChartNoAxesCombined },
]

const stats = [
  { title: 'Total Employees', value: 'API_TOTAL', note: 'From employee database', icon: Users, color: 'blue' },
  { title: 'Present Today', value: '108', note: '87.1% attendance', icon: UserCheck, color: 'green' },
  { title: 'Late Arrivals', value: '12', note: 'Needs attention', icon: Clock3, color: 'orange' },
  { title: 'Absent Today', value: '4', note: '3.2% of workforce', icon: UserX, color: 'red' },
]

function App() {
    const [token, setToken] = useState(
    () => sessionStorage.getItem(TOKEN_KEY) || ''
  )
  const [loginEmail, setLoginEmail] = useState('')
  const [loginPassword, setLoginPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [loginLoading, setLoginLoading] = useState(false)
  const [authReady, setAuthReady] = useState(false)
  const [currentUser, setCurrentUser] = useState(null)
  const [active, setActive] = useState('Dashboard')
  useEffect(() => {
    if (
      authReady &&
      token &&
      currentUser?.role === 'employee' &&
      ['Employees', 'Analytics'].includes(active)
    ) {
      setActive('Attendance')
    }
  }, [authReady, token, currentUser?.role, active])

  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [employees, setEmployees] = useState([])
  const [allEmployeesForLookup, setAllEmployeesForLookup] = useState([])
  const [employeesTotal, setEmployeesTotal] = useState(0)
  const [employeesPage, setEmployeesPage] = useState(1)
  const EMPLOYEES_PAGE_SIZE = 5
  const [loading, setLoading] = useState(true)
  const [apiError, setApiError] = useState('')

  const [attendanceRecords, setAttendanceRecords] = useState([])
  const [attendanceTotal, setAttendanceTotal] = useState(0)
  const [attendancePage, setAttendancePage] = useState(1)
  const ATTENDANCE_PAGE_SIZE = 5
  const [departmentData, setDepartmentData] = useState([])
  const [trendData, setTrendData] = useState([])
  const [lateLeaderboard, setLateLeaderboard] = useState([])
  const [analyticsLoading, setAnalyticsLoading] = useState(true)
  const [analyticsError, setAnalyticsError] = useState('')
  const [analyticsDepartmentFilter, setAnalyticsDepartmentFilter] = useState('All')
  const [analyticsSearch, setAnalyticsSearch] = useState('')
  const [leaderboardSort, setLeaderboardSort] = useState('desc')
  const [attendanceLoading, setAttendanceLoading] = useState(true)
  const [attendanceError, setAttendanceError] = useState('')
  const [employeeProfile, setEmployeeProfile] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [punchLoading, setPunchLoading] = useState(false)
  const [punchMessage, setPunchMessage] = useState('')
  const [punchError, setPunchError] = useState('')

    const handleLogin = async (event) => {
    event.preventDefault()
    setLoginError('')
    setLoginLoading(true)

    try {
      const response = await axios.post(`${API_URL}/auth/login`, {
        email: loginEmail,
        password: loginPassword,
      })

      const accessToken = response.data.access_token

      if (!accessToken) {
        throw new Error('Login response did not contain an access token.')
      }

      sessionStorage.setItem(TOKEN_KEY, accessToken)
      setAuthReady(false)
      setToken(accessToken)
      setCurrentUser(response.data.user || null)
      setLoginPassword('')
    } catch (error) {
      setLoginError(
        error.response?.data?.detail || 'Login failed. Please check your credentials.'
      )
    } finally {
      setLoginLoading(false)
    }
  }

  const [profileOpen, setProfileOpen] = useState(false)

  const handleLogout = () => {
    sessionStorage.removeItem(TOKEN_KEY)
    setToken('')
    setCurrentUser(null)
    setAuthReady(false)
    setEmployees([])
    setAllEmployeesForLookup([])
    setEmployeesTotal(0)
    setLoginPassword('')
    setLoginError('')
  }

  useEffect(() => {
    let cancelled = false

    if (!token) {
      setAuthReady(true)
      return () => { cancelled = true }
    }

    axios.get(`${API_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((response) => {
        if (cancelled) return
        setCurrentUser(response.data)
        setAuthReady(true)
      })
      .catch(() => {
        if (cancelled) return
        sessionStorage.removeItem(TOKEN_KEY)
        setToken('')
        setCurrentUser(null)
        setAuthReady(true)
      })

    return () => { cancelled = true }
  }, [token])

  useEffect(() => {
    if (!authReady || !token || currentUser?.role !== 'admin') {
      setDepartmentData([])
      setTrendData([])
      setLateLeaderboard([])
      setAnalyticsLoading(false)
      setAnalyticsError('')
      return
    }

    const headers = {
      Authorization: `Bearer ${token}`,
    }

    const month = new Date().toISOString().slice(0, 7)
    axios.get(`${API_URL}/analytics/departments/summary`, {
      params: { month },
      headers,
    })
      .then(response => setDepartmentData(response.data.items || []))
      .catch(() => setDepartmentData([]))

    const now = new Date()
    const to = [
      now.getFullYear(),
      String(now.getMonth() + 1).padStart(2, '0'),
      String(now.getDate()).padStart(2, '0'),
    ].join('-')
    const from = `${to.slice(0, 7)}-01`

    axios.get(`${API_URL}/analytics/departments/Engineering/trend`, {
      params: { from, to },
      headers,
    })
      .then(response => setTrendData(response.data.items || []))
      .catch(() => setTrendData([]))

    axios.get(`${API_URL}/analytics/leaderboard/late`, {
      params: { month },
      headers,
    })
      .then(response => {
        setLateLeaderboard(response.data.items || [])
        setAnalyticsError('')
      })
      .catch(() => setAnalyticsError('Unable to load the late-arrival leaderboard.'))
      .finally(() => setAnalyticsLoading(false))
  }, [authReady, token, currentUser?.role])

  useEffect(() => {
    if (!authReady || !token || currentUser?.role !== 'admin') {
      setEmployees([])
      setEmployeesTotal(0)
      setLoading(false)
      setApiError('')
      return
    }

    let cancelled = false
    setLoading(true)
    setApiError('')

    axios.get(`${API_URL}/employees`, {
      params: {
        page: employeesPage,
        page_size: EMPLOYEES_PAGE_SIZE,
        search,
      },
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(response => {
        if (cancelled) return
        setEmployees(response.data.items || [])
        setEmployeesTotal(response.data.total || 0)
      })
      .catch(() => {
        if (!cancelled) setApiError('Unable to load employees. Please check your login session.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [employeesPage, search, token, authReady, currentUser?.role])

  useEffect(() => {
    if (!authReady || !token || currentUser?.role !== 'admin') {
      setAllEmployeesForLookup([])
      return
    }

    let cancelled = false

    axios.get(`${API_URL}/employees`, {
      params: { page: 1, page_size: 100 },
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(response => {
        if (!cancelled) setAllEmployeesForLookup(response.data.items || [])
      })
      .catch(() => {
        if (!cancelled) setAllEmployeesForLookup([])
      })

    return () => {
      cancelled = true
    }
  }, [token, authReady, currentUser?.role])

  useEffect(() => {
    if (!authReady || !token) return

    setAttendanceLoading(true)
    setAttendanceError('')

    axios.get(`${API_URL}/attendance`, {
      params: {
        page: attendancePage,
        page_size: ATTENDANCE_PAGE_SIZE,
        search,
      },
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
      .then(response => {
        setAttendanceRecords(response.data.items || [])
        setAttendanceTotal(response.data.total || 0)
      })
      .catch(() => setAttendanceError('Unable to load attendance records.'))
      .finally(() => setAttendanceLoading(false))
  }, [attendancePage, search, authReady, token])

  useEffect(() => {
    if (!authReady || !token || currentUser?.role !== 'employee') {
      setEmployeeProfile(null)
      return
    }

    let cancelled = false
    setProfileLoading(true)

    axios.get(`${API_URL}/employees/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(response => {
        if (!cancelled) setEmployeeProfile(response.data)
      })
      .catch(error => {
        if (!cancelled) {
          setPunchError(
            error.response?.data?.detail || 'Unable to load your employee profile.'
          )
        }
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false)
      })

    return () => { cancelled = true }
  }, [authReady, token, currentUser?.role])

  const refreshMyAttendance = async () => {
    const response = await axios.get(`${API_URL}/attendance`, {
      params: { page: 1, page_size: 5 },
      headers: { Authorization: `Bearer ${token}` },
    })
    setAttendanceRecords(response.data.items || [])
    setAttendanceTotal(response.data.total || 0)
  }

  const handlePunch = async (action) => {
    const empCode = employeeProfile?.emp_code || currentUser?.emp_code
    if (!empCode || punchLoading) return

    setPunchLoading(true)
    setPunchMessage('')
    setPunchError('')

    try {
      const response = await axios.post(
        `${API_URL}/attendance/${action}`,
        { emp_code: empCode },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      await refreshMyAttendance()
      setPunchMessage(
        action === 'punch-in'
          ? `Punch In recorded at ${formatTime(response.data.punch_in)}.`
          : `Punch Out recorded at ${formatTime(response.data.punch_out)}.`
      )
    } catch (error) {
      setPunchError(
        error.response?.data?.detail ||
        `Unable to ${action === 'punch-in' ? 'punch in' : 'punch out'}. Please try again.`
      )
    } finally {
      setPunchLoading(false)
    }
  }

  const today = new Date()
  const todayKey = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, '0'),
    String(today.getDate()).padStart(2, '0'),
  ].join('-')

  const todayRecords = attendanceRecords.filter(item => item.date === todayKey)
  const employeeByCode = Object.fromEntries(
    allEmployeesForLookup.map(employee => [employee.emp_code, employee])
  )

  const filtered = attendanceRecords.map(record => ({
    ...record,
    ...(employeeByCode[record.emp_code] || {}),
    emp_code: record.emp_code,
    date: record.date,
    status: record.status,
    punch_in: record.punch_in,
    punch_out: record.punch_out,
  }))

  const filteredEmployees = employees

  const presentCount = todayRecords.filter(item =>
    ['PRESENT', 'LATE', 'HALF_DAY'].includes(item.status)
  ).length
  const lateCount = todayRecords.filter(item => (item.late_minutes || 0) > 0).length
  const absentCount = todayRecords.filter(item => item.status === 'ABSENT').length

  const displayStats = stats.map(item => {
    if (item.title === 'Total Employees') {
      return { ...item, value: loading ? '...' : apiError ? '—' : String(employeesTotal) }
    }
    if (item.title === 'Present Today') {
      return { ...item, value: attendanceLoading ? '...' : String(presentCount), note: 'Based on today’s records' }
    }
    if (item.title === 'Late Arrivals') {
      return { ...item, value: attendanceLoading ? '...' : String(lateCount), note: 'Records with late minutes' }
    }
    if (item.title === 'Absent Today') {
      return { ...item, value: attendanceLoading ? '...' : String(absentCount), note: 'Explicitly marked absent' }
    }
    return item
  })

  const formatTime = value => value
    ? new Date(value).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })
    : '—'

  const formatWorkDuration = item => {
    if (!item.punch_in || !item.punch_out) return '—'

    const start = new Date(item.punch_in).getTime()
    const end = new Date(item.punch_out).getTime()

    if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) {
      return '—'
    }

    const totalSeconds = Math.floor((end - start) / 1000)
    if (totalSeconds < 60) return `${totalSeconds} sec`

    const totalMinutes = Math.floor(totalSeconds / 60)
    const hours = Math.floor(totalMinutes / 60)
    const minutes = totalMinutes % 60

    if (hours && minutes) return `${hours} h ${minutes} min`
    if (hours) return `${hours} h`
    return `${minutes} min`
  }

  const tones = {
    blue: 'bg-blue-50 text-blue-600',
    green: 'bg-emerald-50 text-emerald-600',
    orange: 'bg-orange-50 text-orange-600',
    red: 'bg-rose-50 text-rose-600',
  }



  const filteredAnalyticsLeaderboard = lateLeaderboard
    .filter(item => analyticsDepartmentFilter === 'All' || item.department === analyticsDepartmentFilter)
    .filter(item => {
      const q = analyticsSearch.trim().toLowerCase()
      return !q || [item.name, item.emp_code, item.department].some(value =>
        String(value || '').toLowerCase().includes(q)
      )
    })
    .slice()
    .sort((a, b) => leaderboardSort === 'desc'
      ? Number(b.total_late_minutes || 0) - Number(a.total_late_minutes || 0)
      : Number(a.total_late_minutes || 0) - Number(b.total_late_minutes || 0))

  if (!authReady) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f7fc] text-slate-600">
        Checking your Attendify session...
      </div>
    )
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#f4f7fc] px-4 py-10">
        <form onSubmit={handleLogin} className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 shadow-xl">
          <div className="mb-6 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-600 text-white">
              <CalendarCheck size={26} />
            </div>
            <h1 className="text-2xl font-bold text-slate-900">Attendify</h1>
            <p className="mt-2 text-sm text-slate-500">Sign in to your workforce dashboard</p>
          </div>
          <label htmlFor="login-email" className="mb-1 block text-sm font-medium text-slate-700">Email</label>
          <input id="login-email" type="email" autoComplete="username" required value={loginEmail} onChange={e => setLoginEmail(e.target.value)} className="mb-4 w-full rounded-xl border border-slate-300 px-4 py-3" placeholder="you@example.com" />
          <label htmlFor="login-password" className="mb-1 block text-sm font-medium text-slate-700">Password</label>
          <input id="login-password" type="password" autoComplete="current-password" required value={loginPassword} onChange={e => setLoginPassword(e.target.value)} className="mb-4 w-full rounded-xl border border-slate-300 px-4 py-3" placeholder="Enter your password" />
          {loginError && <p role="alert" className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{String(loginError)}</p>}
          <button type="submit" disabled={loginLoading} className="w-full rounded-xl bg-blue-600 px-4 py-3 font-semibold text-white disabled:opacity-60">
            {loginLoading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#f4f7fc] text-slate-800">
      <aside className={`${menuOpen ? 'flex' : 'hidden'} fixed inset-y-0 left-0 z-20 w-64 flex-col border-r border-slate-800 bg-[#111c35] p-5 text-white shadow-xl shadow-slate-900/10 md:flex`}>
        <div className="mb-10 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-blue-500 text-white shadow-lg shadow-blue-500/30"><CalendarCheck size={23}/></div>
          <div><h1 className="text-lg font-bold tracking-tight text-white">Attendify</h1><p className="text-xs text-slate-400">Workforce management</p></div>
        </div>
        <p className="mb-3 px-3 text-[11px] font-bold uppercase tracking-[0.18em] text-slate-500">Workspace</p>
        <nav className="space-y-2">
          {navigation.filter(({ label }) => currentUser?.role === 'admin' || !['Employees', 'Analytics'].includes(label)).map(({ label, icon: Icon }) => (
            <button key={label} onClick={() => { setActive(label); setMenuOpen(false) }}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition ${active === label ? 'bg-blue-500/15 text-blue-300 ring-1 ring-inset ring-blue-400/20' : 'text-slate-400 hover:bg-white/5 hover:text-white'}`}>
              <Icon size={19}/>{label}
              {label === 'Attendance' && <span className="ml-auto rounded-lg bg-white/10 px-2 py-0.5 text-xs text-slate-300">12</span>}
            </button>
          ))}
        </nav>
        <div className="mt-auto">
          <div className="rounded-2xl border border-white/5 bg-white/5 p-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold"><TrendingUp size={17} className="text-blue-600"/>Attendance insights</div>
            <p className="text-xs leading-5 text-slate-400">Review daily attendance and spot trends across your team.</p>
            {currentUser?.role === 'admin' && (
              <button onClick={() => setActive('Analytics')} className="mt-3 text-sm font-semibold text-blue-600">View reports →</button>
            )}
          </div>
          <button onClick={() => setActive('Settings')} className="mt-5 flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-slate-400 transition hover:bg-white/5 hover:text-white"><Settings size={18}/>Settings</button>
        </div>
      </aside>

      {menuOpen && <button aria-label="Close menu" className="fixed inset-0 z-10 bg-slate-900/20 md:hidden" onClick={() => setMenuOpen(false)}/>}

      <main className="min-h-screen md:ml-64">
        <header className="sticky top-0 z-10 flex h-[76px] items-center justify-between border-b border-slate-200/80 bg-white/95 shadow-sm shadow-slate-200/30 px-4 backdrop-blur md:px-8">
          <div className="flex items-center gap-3">
            <button className="md:hidden" onClick={() => setMenuOpen(true)} aria-label="Open menu"><Menu/></button>
            <div><p className="text-xs text-slate-400">Workspace / {active}</p><h2 className="text-lg font-bold">{active}</h2></div>
          </div>
          <div className="flex items-center gap-3 md:gap-5">
            <button aria-label="Notifications" className="relative rounded-xl p-2 text-slate-500 hover:bg-slate-100"><Bell size={20}/><span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-red-500"/></button>
            <div className="relative">
              <button
                type="button"
                onClick={() => setProfileOpen((open) => !open)}
                aria-expanded={profileOpen}
                aria-label="Admin profile menu"
                className="flex items-center gap-3 rounded-xl p-2 text-left transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-blue-100"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700 ring-1 ring-blue-200">KA</div>
                <div className="hidden sm:block">
                  <p className="text-sm font-semibold text-slate-800">{currentUser?.email || "User"}</p>
                  <p className="text-xs capitalize text-slate-500">{currentUser?.role || "User"}</p>
                </div>
                <ChevronDown size={15} className={`text-slate-400 transition-transform ${profileOpen ? "rotate-180" : ""}`}/>
              </button>

              {profileOpen && (
                <>
                  <button
                    type="button"
                    aria-label="Close profile menu"
                    className="fixed inset-0 z-20 cursor-default"
                    onClick={() => setProfileOpen(false)}
                  />
                  <div className="absolute right-0 top-full z-30 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-900/10">
                    <div className="flex items-center gap-3 rounded-xl bg-slate-50 p-3">
                      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-blue-100 font-bold text-blue-700">KA</div>
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{currentUser?.email || "User"}</p>
                        <p className="text-xs capitalize text-slate-500">{currentUser?.role || "User"}</p>
                      </div>
                    </div>
                    <div className="my-2 border-t border-slate-100"/>
                    <button
                      type="button"
                      onClick={() => {
                        setProfileOpen(false)
                        handleLogout()
                      }}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-red-50 hover:text-red-600"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
                        <path d="m16 17 5-5-5-5"/>
                        <path d="M21 12H9"/>
                      </svg>
                      Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        <div className="mx-auto max-w-[1600px] space-y-7 p-4 md:p-8">
          <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h3 className="text-3xl font-extrabold tracking-tight text-slate-900">
                {active === 'Analytics' ? 'Workforce Analytics' : `Good morning, ${currentUser?.email?.split('@')[0] || 'User'}`}
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                {active === 'Analytics'
                  ? 'Explore department performance and employee punctuality.'
                  : 'Here’s what’s happening with your workforce today.'}
              </p>
            </div>
            <div className="flex items-center gap-2 self-start rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-600"><CalendarCheck size={17} className="text-blue-600"/>{new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}</div>
          </section>

          {active === 'Dashboard' && currentUser?.role === 'employee' ? (
            <section className="space-y-6">
              <div className="rounded-2xl bg-gradient-to-r from-blue-700 to-indigo-600 p-6 text-white shadow-lg">
                <p className="text-sm text-blue-100">Employee self-service</p>
                <h2 className="mt-2 text-2xl font-bold">
                  Welcome, {employeeProfile?.name || currentUser?.email?.split('@')[0] || 'Employee'}
                </h2>
                <p className="mt-2 text-sm text-blue-100">
                  {employeeProfile?.emp_code || currentUser?.emp_code || 'Employee code'}
                  {employeeProfile?.department ? ` · ${employeeProfile.department}` : ''}
                </p>
              </div>

              {punchError && (
                <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  {String(punchError)}
                </p>
              )}
              {punchMessage && (
                <p role="status" className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                  {punchMessage}
                </p>
              )}

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <p className="text-sm text-slate-500">Today's attendance</p>
                  <p className="mt-2 text-2xl font-bold text-slate-900">
                    {attendanceLoading ? 'Loading...' :
                      (attendanceRecords.find(item => item.date === todayKey)?.status || 'Not punched in')}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">
                    Punch In: {formatTime(attendanceRecords.find(item => item.date === todayKey)?.punch_in)}
                  </p>
                  <p className="mt-1 text-sm text-slate-500">
                    Punch Out: {formatTime(attendanceRecords.find(item => item.date === todayKey)?.punch_out)}
                  </p>
                  <div className="mt-5 flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled={punchLoading || profileLoading || !employeeProfile?.emp_code || Boolean(attendanceRecords.find(item => item.date === todayKey))}
                      onClick={() => handlePunch('punch-in')}
                      className="rounded-xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {punchLoading ? 'Processing...' : 'Punch In'}
                    </button>
                    <button
                      type="button"
                      disabled={punchLoading || !attendanceRecords.find(item => item.date === todayKey && item.punch_in && !item.punch_out)}
                      onClick={() => handlePunch('punch-out')}
                      className="rounded-xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {punchLoading ? 'Processing...' : 'Punch Out'}
                    </button>
                  </div>
                  <p className="mt-3 text-xs text-slate-400">
                    Punch buttons become available according to today's recorded attendance.
                  </p>
                </div>

                <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                  <h3 className="font-bold text-slate-900">My Profile</h3>
                  {profileLoading ? (
                    <p className="mt-4 text-sm text-slate-500">Loading profile...</p>
                  ) : (
                    <dl className="mt-4 space-y-4 text-sm">
                      <div>
                        <dt className="text-slate-500">Full name</dt>
                        <dd className="mt-1 font-medium text-slate-900">{employeeProfile?.name || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Email</dt>
                        <dd className="mt-1 break-all font-medium text-slate-900">{employeeProfile?.email || currentUser?.email || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Department</dt>
                        <dd className="mt-1 font-medium text-slate-900">{employeeProfile?.department || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Employee code</dt>
                        <dd className="mt-1 font-medium text-slate-900">{employeeProfile?.emp_code || '—'}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Shift timing</dt>
                        <dd className="mt-1 font-medium text-slate-900">
                          {employeeProfile?.shift_start || '—'} – {employeeProfile?.shift_end || '—'}
                        </dd>
                      </div>
                    </dl>
                  )}
                </div>
              </div>

              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="p-6">
                  <h3 className="font-bold text-slate-900">My Recent Attendance</h3>
                  <p className="mt-1 text-sm text-slate-500">Your latest attendance records</p>
                </div>
                {attendanceLoading ? (
                  <p className="px-6 pb-6 text-sm text-slate-500">Loading attendance...</p>
                ) : attendanceError ? (
                  <p role="alert" className="px-6 pb-6 text-sm text-red-600">{attendanceError}</p>
                ) : attendanceRecords.length === 0 ? (
                  <p className="px-6 pb-6 text-sm text-slate-500">No attendance records found yet.</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                        <tr>
                          <th className="px-6 py-3">Date</th>
                          <th className="px-6 py-3">Status</th>
                          <th className="px-6 py-3">Punch In</th>
                          <th className="px-6 py-3">Punch Out</th>
                          <th className="px-6 py-3">Hours</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {attendanceRecords.map((item, index) => (
                          <tr key={`${item.date}-${index}`}>
                            <td className="px-6 py-4">{item.date}</td>
                            <td className="px-6 py-4">{item.status || '—'}</td>
                            <td className="px-6 py-4">{formatTime(item.punch_in)}</td>
                            <td className="px-6 py-4">{formatTime(item.punch_out)}</td>
                            <td className="px-6 py-4">{formatWorkDuration(item)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          ) : active === 'Dashboard' ? <>
            <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {displayStats.map(({ title, value, note, icon: Icon, color }) => (
                <div key={title} className="group rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-200/50 transition-all duration-200 hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-lg hover:shadow-slate-200/60">
                  <div className="flex items-start justify-between"><p className="text-sm font-medium text-slate-500">{title}</p><div className={`rounded-2xl p-3 shadow-sm transition-transform duration-200 group-hover:scale-105 ${tones[color]}`}><Icon size={20}/></div></div>
                  <p className="mt-5 text-4xl font-extrabold tracking-tight text-slate-900">{value}</p><p className="mt-2 text-xs text-slate-500">{note}</p>
                </div>
              ))}
            </section>

            <section className="grid gap-6 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm shadow-slate-200/50 xl:col-span-2">
                <div className="flex items-start justify-between"><div><h3 className="text-base font-bold tracking-tight text-slate-900">Attendance overview</h3><p className="mt-1 text-sm text-slate-500">Engineering · daily attendance rate (live API)</p></div><span className="rounded-lg bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600">This week <ChevronDown size={13} className="ml-1 inline"/></span></div>
                <div className="mt-8 grid grid-cols-[38px_minmax(0,1fr)] gap-3">
                  <div className="flex h-52 flex-col justify-between pb-7 text-right text-[11px] font-medium text-slate-400">
                    <span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span>
                  </div>
                  <div className="relative h-52">
                    <div className="absolute inset-x-0 top-0 bottom-7 flex flex-col justify-between">
                      {[100, 75, 50, 25, 0].map(level => (
                        <div key={level} className="w-full border-t border-dashed border-slate-200" />
                      ))}
                    </div>
                    <div className="relative flex h-full justify-around gap-3">
                      {trendData.slice(-7).map(item => {
                        const rate = item.attendance_rate
                        const height = rate == null ? null : Math.max(0, Math.min(100, rate * 100))
                        const day = new Date(`${item.date}T12:00:00`).toLocaleDateString('en-IN', { weekday: 'short' })
                        return (
                          <div key={item.date} className="z-[1] flex min-w-0 flex-1 flex-col items-center">
                            <div className="relative flex h-[calc(100%-28px)] w-full items-end justify-center">
                              {height === null ? (
                                <div className="absolute bottom-0 w-3/4 border-t-2 border-dashed border-slate-300" title={`${item.date}: No attendance data`} />
                              ) : (
                                <>
                                  {height > 0 && <span className="absolute z-10 text-[11px] font-bold text-blue-700" style={{ bottom: `${height}%`, transform: 'translateY(-5px)' }}>{Math.round(height)}%</span>}
                                  <div className="w-1/2 max-w-10 rounded-t-lg bg-gradient-to-t from-blue-600 to-sky-400 shadow-sm shadow-blue-500/20 transition-all duration-300 hover:from-blue-700 hover:to-sky-500" style={{ height: `${height}%`, minHeight: height > 0 ? '4px' : '0' }} title={`${item.date}: ${Math.round(height)}% attendance`} />
                                </>
                              )}
                            </div>
                            <span className="mt-2 text-[11px] font-medium text-slate-500">{day}</span>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
                <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                  <span className="h-2.5 w-2.5 rounded-sm bg-blue-500" />Attendance rate
                  <span className="ml-auto text-slate-400">Last 7 days</span>
                </div>
              </div>
              <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm shadow-slate-200/50">
                <h3 className="text-base font-bold tracking-tight text-slate-900">Attendance breakdown</h3><p className="mt-1 text-sm text-slate-500">Today's recorded attendance status</p>
                {(() => {
                  const present = todayRecords.filter(item => ['PRESENT', 'LATE', 'HALF_DAY'].includes(item.status)).length
                  const late = todayRecords.filter(item => (item.late_minutes || 0) > 0).length
                  const absent = todayRecords.filter(item => item.status === 'ABSENT').length
                  const total = present + absent
                  const rate = total ? Math.round((present / total) * 100) : null
                  const presentEnd = total ? (present / total) * 100 : 0
                  const absentEnd = total ? presentEnd + (absent / total) * 100 : 0
                  const lateEnd = total ? Math.min(100, presentEnd + (late / total) * 100) : 0
                  const segments = total
                    ? `conic-gradient(#2563eb 0% ${presentEnd}%, #f59e0b ${presentEnd}% ${lateEnd}%, #e2e8f0 ${lateEnd}% 100%)`
                    : '#e2e8f0'
                  return <>
                    <div className="my-7 flex justify-center">
                      <div className="relative flex h-40 w-40 items-center justify-center rounded-full" style={{ background: segments }}>
                        <div className="flex h-28 w-28 flex-col items-center justify-center rounded-full bg-white">
                          <span className="text-3xl font-bold">{rate === null ? '—' : `${rate}%`}</span>
                          <span className="text-xs text-slate-400">Recorded presence</span>
                        </div>
                      </div>
                    </div>
                    {[
                      ['Present', present, 'bg-blue-600'],
                      ['Late (included in present)', late, 'bg-amber-500'],
                      ['Absent', absent, 'bg-slate-300'],
                    ].map(([label, value, color]) => (
                      <div key={label} className="flex items-center justify-between border-t border-slate-100 py-3 text-sm">
                        <span className="flex items-center gap-2 text-slate-500"><span className={`h-2.5 w-2.5 rounded-full ${color}`}/>{label}</span>
                        <span className="font-semibold">{value}</span>
                      </div>
                    ))}
                    {total === 0 && <p className="mt-2 text-xs text-slate-400">No present or absent records are available for today.</p>}
                  </>
                })()}
              </div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50">
              <div className="flex flex-col justify-between gap-4 p-6 sm:flex-row sm:items-center">
                <div><h3 className="text-base font-bold tracking-tight text-slate-900">Recent attendance</h3><p className="mt-1 text-sm text-slate-500">Latest employee attendance records</p></div>
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5"><Search size={17} className="text-slate-400"/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search employees..." className="w-full bg-transparent text-sm outline-none sm:w-48"/></label>
              </div>
              <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400"><tr>{['Employee', 'Department', 'Punch in', 'Punch out', 'Status'].map(h => <th key={h} className="px-6 py-4 font-semibold">{h}</th>)}</tr></thead>
                <tbody className="divide-y divide-slate-100">
                  {attendanceLoading ? (
                    <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-400">Loading attendance...</td></tr>
                  ) : attendanceError ? (
                    <tr><td colSpan="5" className="px-6 py-10 text-center text-rose-500">{attendanceError}</td></tr>
                  ) : filtered.length === 0 ? (
                    <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-400">No attendance records found.</td></tr>
                  ) : filtered.map(item => (
                    <tr key={`${item.emp_code}-${item.date}`} className="transition-colors duration-150 hover:bg-blue-50/60">
                      <td className="px-6 py-4">
                        <div className="font-semibold">{item.name || 'Unknown employee'}</div>
                        <div className="mt-1 text-xs text-slate-400">{item.emp_code}</div>
                        <div className="mt-1 text-xs text-slate-400">{item.date}</div>
                      </td>
                      <td className="px-6 py-4 text-slate-500">{item.department || '—'}</td>
                      <td className="px-6 py-4 text-slate-600">{formatTime(item.punch_in)}</td>
                      <td className="px-6 py-4 text-slate-600">{formatTime(item.punch_out)}</td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-bold tracking-wide ${
                          item.status === 'PRESENT' ? 'bg-emerald-50 text-emerald-700' :
                          item.status === 'LATE' ? 'bg-amber-50 text-amber-700' :
                          item.status === 'ABSENT' ? 'bg-rose-50 text-rose-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>{item.status.replaceAll('_', ' ')}</span>
                        {item.late_minutes > 0 && <div className="mt-1 text-xs text-amber-600">{item.late_minutes} min late</div>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <div className="border-t border-slate-100 px-6 py-4 text-xs text-slate-400">Showing {filtered.length} attendance records from API</div>
            </section>

            <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50">
              <div className="p-6">
                <h3 className="text-base font-bold tracking-tight text-slate-900">Department Analytics</h3>
                <p className="mt-1 text-sm text-slate-500">
                  Monthly attendance summary · {new Date().toLocaleDateString('en-CA').slice(0, 7)}
                </p>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[600px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      {['Department', 'Headcount', 'Late count', 'Avg. work hours'].map(label =>
                        <th key={label} className="px-6 py-4 font-semibold">{label}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {departmentData.length === 0 ? (
                      <tr>
                        <td colSpan="4" className="px-6 py-8 text-center text-slate-400">
                          No department analytics available.
                        </td>
                      </tr>
                    ) : departmentData.map(item => (
                      <tr key={item.department} className="transition-colors duration-150 hover:bg-blue-50/60">
                        <td className="px-6 py-4 font-medium">{item.department}</td>
                        <td className="px-6 py-4 text-slate-600">{item.headcount}</td>
                        <td className="px-6 py-4 text-slate-600">{item.late_count}</td>
                        <td className="px-6 py-4 text-slate-600">
                          {Number(item.avg_work_hours || 0).toFixed(2)} hrs
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </> : active === 'Employees' ? (
            <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50">
              <div className="flex flex-col justify-between gap-4 p-6 sm:flex-row sm:items-center">
                <div>
                  <h3 className="font-bold">All Employees</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {loading ? 'Loading employee records...' : `${employeesTotal} employees from the database`}
                  </p>
                </div>
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5">
                  <Search size={17} className="text-slate-400"/>
                  <input value={search} onChange={e => {
                    setSearch(e.target.value)
                    setEmployeesPage(1)
                  }}
                    placeholder="Search employees..."
                    className="w-full bg-transparent text-sm outline-none sm:w-56"/>
                </label>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[650px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      {['Employee', 'Employee Code', 'Department', 'Email', 'Shift'].map(label =>
                        <th key={label} className="px-6 py-4 font-semibold">{label}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {loading ? (
                      <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-400">Loading employees...</td></tr>
                    ) : apiError ? (
                      <tr><td colSpan="5" className="px-6 py-10 text-center text-rose-500">{apiError}</td></tr>
                    ) : filteredEmployees.length === 0 ? (
                      <tr><td colSpan="5" className="px-6 py-10 text-center text-slate-400">No matching employees found.</td></tr>
                    ) : filteredEmployees.map(employee => (
                      <tr key={employee.emp_code} className="transition-colors duration-150 hover:bg-blue-50/60">
                        <td className="px-6 py-4 font-semibold">{employee.name}</td>
                        <td className="px-6 py-4 text-slate-500">{employee.emp_code}</td>
                        <td className="px-6 py-4 text-slate-500">{employee.department || '—'}</td>
                        <td className="px-6 py-4 text-slate-500">{employee.email || '—'}</td>
                        <td className="px-6 py-4 text-slate-500">
                          {employee.shift_start || '—'} – {employee.shift_end || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-col gap-3 border-t border-slate-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-500">
                  {employeesTotal === 0
                    ? 'Showing 0 employees'
                    : `Showing ${(employeesPage - 1) * EMPLOYEES_PAGE_SIZE + 1}–${Math.min(employeesPage * EMPLOYEES_PAGE_SIZE, employeesTotal)} of ${employeesTotal}`}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={employeesPage === 1 || loading}
                    onClick={() => setEmployeesPage(page => Math.max(1, page - 1))}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="px-2 text-sm text-slate-600">
                    Page {employeesPage} of {Math.max(1, Math.ceil(employeesTotal / EMPLOYEES_PAGE_SIZE))}
                  </span>
                  <button
                    type="button"
                    disabled={employeesPage >= Math.ceil(employeesTotal / EMPLOYEES_PAGE_SIZE) || loading}
                    onClick={() => setEmployeesPage(page => page + 1)}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            </section>
          ) : active === 'Attendance' ? (
            <section className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm shadow-slate-200/50">
              <div className="flex flex-col justify-between gap-4 p-6 sm:flex-row sm:items-center">
                <div>
                  <h3 className="font-bold">Attendance Records</h3>
                  <p className="mt-1 text-sm text-slate-500">
                    {attendanceLoading ? 'Loading records...' : `${attendanceTotal} attendance records from the database`}
                  </p>
                </div>
                <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2.5">
                  <Search size={17} className="text-slate-400"/>
                  <input value={search} onChange={e => {
                    setSearch(e.target.value)
                    setAttendancePage(1)
                  }}
                    placeholder="Search attendance..."
                    className="w-full bg-transparent text-sm outline-none sm:w-56"/>
                </label>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[850px] text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      {['Employee', 'Department', 'Date', 'Punch in', 'Punch out', 'Status', 'Work hours'].map(label =>
                        <th key={label} className="px-5 py-4 font-semibold">{label}</th>
                      )}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {attendanceLoading ? (
                      <tr><td colSpan="7" className="px-6 py-10 text-center text-slate-400">Loading attendance records...</td></tr>
                    ) : attendanceError ? (
                      <tr><td colSpan="7" className="px-6 py-10 text-center text-rose-500">{attendanceError}</td></tr>
                    ) : filtered.length === 0 ? (
                      <tr><td colSpan="7" className="px-6 py-10 text-center text-slate-400">No matching attendance records.</td></tr>
                    ) : filtered.map(item => (
                      <tr key={`${item.emp_code}-${item.date}`} className="transition-colors duration-150 hover:bg-blue-50/60">
                        <td className="px-5 py-4">
                          <div className="font-semibold">{item.name || 'Unknown employee'}</div>
                          <div className="mt-1 text-xs text-slate-400">{item.emp_code}</div>
                        </td>
                        <td className="px-5 py-4 text-slate-500">{item.department || '—'}</td>
                        <td className="px-5 py-4 text-slate-500">{item.date}</td>
                        <td className="px-5 py-4 text-slate-500">{formatTime(item.punch_in)}</td>
                        <td className="px-5 py-4 text-slate-500">{formatTime(item.punch_out)}</td>
                        <td className="px-5 py-4">
                          <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-bold tracking-wide ${
                            item.status === 'PRESENT' ? 'bg-emerald-50 text-emerald-700' :
                            item.status === 'ABSENT' ? 'bg-rose-50 text-rose-700' :
                            item.status === 'LEAVE' ? 'bg-slate-100 text-slate-600' :
                            'bg-amber-50 text-amber-700'
                          }`}>{item.status.replaceAll('_', ' ')}</span>
                          {item.late_minutes > 0 && <div className="mt-1 text-xs text-amber-600">{item.late_minutes} min late</div>}
                          {item.half_day && <div className="mt-1 text-xs text-slate-500">Half-day</div>}
                        </td>
                        <td className="px-5 py-4 text-slate-600">{formatWorkDuration(item)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex flex-col gap-3 border-t border-slate-100 px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-500">
                  {attendanceTotal === 0
                    ? 'Showing 0 attendance records'
                    : `Showing ${(attendancePage - 1) * ATTENDANCE_PAGE_SIZE + 1}–${Math.min(attendancePage * ATTENDANCE_PAGE_SIZE, attendanceTotal)} of ${attendanceTotal}`}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={attendancePage === 1 || attendanceLoading}
                    onClick={() => setAttendancePage(page => Math.max(1, page - 1))}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="px-2 text-sm text-slate-600">
                    Page {attendancePage} of {Math.max(1, Math.ceil(attendanceTotal / ATTENDANCE_PAGE_SIZE))}
                  </span>
                  <button
                    type="button"
                    disabled={attendancePage >= Math.ceil(attendanceTotal / ATTENDANCE_PAGE_SIZE) || attendanceLoading}
                    onClick={() => setAttendancePage(page => page + 1)}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium transition hover:border-blue-300 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            </section>
          ) : active === 'Analytics' ? (
            <div className="space-y-7">
              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  { label: 'Total Employees', value: departmentData.reduce((sum, item) => sum + Number(item.headcount || 0), 0), note: 'Across departments', color: 'text-blue-700', icon: Users },
                  { label: 'Departments', value: departmentData.length, note: 'In monthly summary', color: 'text-indigo-700', icon: ChartNoAxesCombined },
                  { label: 'Late Arrivals', value: departmentData.reduce((sum, item) => sum + Number(item.late_count || 0), 0), note: 'Recorded this month', color: 'text-amber-700', icon: Clock3 },
                  { label: 'Avg. Department Hours', value: departmentData.some(item => item.avg_work_hours != null) ? `${(departmentData.filter(item => item.avg_work_hours != null).reduce((sum, item) => sum + Number(item.avg_work_hours), 0) / departmentData.filter(item => item.avg_work_hours != null).length).toFixed(2)} h` : '—', note: 'Mean of available department averages', color: 'text-emerald-700', icon: TrendingUp },
                ].map(({ label, value, note, color, icon: MetricIcon }) => (
                  <article key={label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium text-slate-500">{label}</p>
                      <span className={`rounded-xl bg-slate-50 p-2 ${color}`}><MetricIcon size={19} /></span>
                    </div>
                    <p className={`mt-4 text-3xl font-extrabold tracking-tight ${color}`}>{value}</p>
                    <p className="mt-1 text-xs text-slate-400">{note}</p>
                  </article>
                ))}
              </section>

              <section className="grid gap-6 xl:grid-cols-2">
                <article className="rounded-3xl border border-blue-100 bg-white p-6 shadow-sm">
                  <h3 className="font-bold text-slate-900">Department Late Arrivals</h3>
                  <p className="mt-1 mb-6 text-sm text-slate-500">Recorded late arrivals by department</p>
                  <div className="space-y-5">
                    {departmentData.map(item => (
                      <div key={item.department}>
                        <div className="mb-2 flex items-center justify-between text-sm">
                          <span className="font-medium text-slate-700">{item.department}</span>
                          <span className="font-bold text-slate-900">{Number(item.late_count || 0)}</span>
                        </div>
                        <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500" style={{ width: `${Number(item.late_count || 0) / Math.max(1, ...departmentData.map(d => Number(d.late_count || 0))) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                    {departmentData.length === 0 && <p className="py-6 text-center text-sm text-slate-400">{analyticsLoading ? 'Loading chart data...' : 'No department data available.'}</p>}
                  </div>
                </article>

                <article className="rounded-3xl border border-emerald-100 bg-white p-6 shadow-sm">
                  <h3 className="font-bold text-slate-900">Average Working Hours</h3>
                  <p className="mt-1 mb-6 text-sm text-slate-500">Average hours by department</p>
                  <div className="space-y-5">
                    {departmentData.map(item => (
                      <div key={item.department}>
                        <div className="mb-2 flex items-center justify-between text-sm">
                          <span className="font-medium text-slate-700">{item.department}</span>
                          <span className="font-bold text-slate-900">{Number(item.avg_work_hours || 0).toFixed(2)} h</span>
                        </div>
                        <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all duration-500" style={{ width: `${Number(item.avg_work_hours || 0) / Math.max(1, ...departmentData.map(d => Number(d.avg_work_hours || 0))) * 100}%` }} />
                        </div>
                      </div>
                    ))}
                    {departmentData.length === 0 && <p className="py-6 text-center text-sm text-slate-400">{analyticsLoading ? 'Loading chart data...' : 'No department data available.'}</p>}
                  </div>
                </article>
              </section>
              <section className="rounded-3xl border border-blue-100/80 bg-gradient-to-br from-white via-white to-blue-50/50 p-7 shadow-sm shadow-blue-950/5">
                <div className="mb-5">
                  <h3 className="text-lg font-bold tracking-tight text-slate-900">Monthly Department Analytics</h3>
                  <p className="mt-1.5 text-sm text-slate-500">October 2026 · Live API summary</p><p className="mt-2 text-xs text-slate-400">Select a department card to filter the leaderboard.</p>
                </div>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {departmentData.map(item => (
                    <button
                      key={item.department}
                      type="button"
                      onClick={() => setAnalyticsDepartmentFilter(current => current === item.department ? 'All' : item.department)}
                      className={`rounded-2xl border bg-gradient-to-br from-white to-slate-50/70 min-h-[185px] p-6 text-left shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 ${
                        analyticsDepartmentFilter === item.department
                          ? 'border-blue-500 bg-gradient-to-br from-blue-50/80 via-white to-indigo-50/60 ring-2 ring-blue-100 shadow-md shadow-blue-100/50'
                          : 'border-slate-200/80'
                      }`}
                    >
                      <p className="text-sm font-semibold tracking-wide text-slate-600">{item.department}</p>
                      <p className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900">{item.headcount}</p>
                      <p className="text-xs font-medium text-slate-400">Employees</p>
                      <div className="mt-4 grid grid-cols-2 gap-3 border-t border-blue-100/70 pt-4">
                        <div>
                          <p className="text-xs text-slate-500">Late count</p>
                          <p className="mt-1 font-semibold">{item.late_count}</p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Avg. work hours</p>
                          <p className="mt-1 font-semibold">{Number(item.avg_work_hours || 0).toFixed(2)} h</p>
                        </div>
                      </div>
                    </button>
                  ))}
                  {departmentData.length === 0 && (
                    <p className="text-sm text-slate-500">
                      {analyticsLoading ? 'Loading department analytics...' : 'No department summary available.'}
                    </p>
                  )}
                </div>
              </section>

              <section className="overflow-hidden rounded-3xl border border-blue-100/80 bg-white shadow-sm shadow-blue-950/5">
                <div className="p-6">
                  <h3 className="text-lg font-bold tracking-tight text-slate-900">Late Arrival Leaderboard</h3>
                  <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                    <input
                      type="search"
                      value={analyticsSearch}
                      onChange={event => setAnalyticsSearch(event.target.value)}
                      placeholder="Search employee, code or department..."
                      className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-slate-50/50 px-4 py-3 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
                    />
                    <select
                      value={analyticsDepartmentFilter}
                      onChange={event => setAnalyticsDepartmentFilter(event.target.value)}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-500/10"
                    >
                      <option value="All">All departments</option>
                      {[...new Set(departmentData.map(item => item.department))].map(department => (
                        <option key={department} value={department}>{department}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => setLeaderboardSort(current => current === 'desc' ? 'asc' : 'desc')}
                      className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                    >
                      Late minutes: {leaderboardSort === 'desc' ? 'Highest first ↓' : 'Lowest first ↑'}
                    </button>
                  </div>
                  <p className="mt-1 text-sm text-slate-500">Employees ranked by total late minutes for October 2026</p>
                  {analyticsError && <p className="mt-3 text-sm text-rose-500">{analyticsError}</p>}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[650px] text-left text-sm">
                    <thead className="bg-gradient-to-r from-blue-50/80 to-indigo-50/60 text-xs uppercase tracking-wider text-slate-500">
                      <tr>
                        {['Rank', 'Employee', 'Department', 'Employee code', 'Late minutes'].map(label =>
                          <th key={label} className="px-6 py-4 font-semibold">{label}</th>
                        )}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {analyticsLoading ? (
                        <tr><td colSpan="5" className="px-6 py-8 text-center text-slate-400">Loading leaderboard...</td></tr>
                      ) : filteredAnalyticsLeaderboard.length === 0 ? (
                        <tr><td colSpan="5" className="px-6 py-8 text-center text-slate-400">No late arrivals found for this month.</td></tr>
                      ) : filteredAnalyticsLeaderboard.map((item, index) => (
                        <tr key={item.emp_code} className="transition-colors hover:bg-gradient-to-r hover:from-blue-50/70 hover:to-indigo-50/30">
                          <td className="px-6 py-4 font-semibold">#{index + 1}</td>
                          <td className="px-6 py-4 font-medium">{item.name}</td>
                          <td className="px-6 py-4 text-slate-500">{item.department}</td>
                          <td className="px-6 py-4 text-slate-500">{item.emp_code}</td>
                          <td className="px-6 py-4"><span className="inline-flex rounded-full border border-amber-200/70 bg-gradient-to-r from-amber-50 to-orange-50 px-3 py-1.5 text-xs font-bold text-amber-700 shadow-sm shadow-amber-100/50">{item.total_late_minutes} min</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </div>
          ) : <section className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600"><CalendarCheck size={25}/></div>
            <h3 className="mt-4 text-xl font-bold">{active}</h3><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">The {active.toLowerCase()} section is ready for the next implementation step. We’ll connect it to your FastAPI endpoints next.</p>
            <button onClick={() => setActive('Dashboard')} className="mt-5 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700">Back to dashboard</button>
          </section>}
          <footer className="pb-2 text-center text-xs text-slate-400">Attendify · Employee Attendance & Analytics</footer>
        </div>
      </main>
    </div>
  )
}

export default App
