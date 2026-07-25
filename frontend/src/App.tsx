import React from 'react'
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom'
import { Login } from './components/Login'
import { Register } from './components/Register'
import { Home } from './components/Home'
import { LogPeriod } from './components/LogPeriod'
import { CalendarView } from './components/CalendarView'
import { NotificationSettings } from './components/NotificationSettings'
import { authService } from './api'
import './App.css'

const RootRedirect: React.FC = () => {
  return authService.isAuthenticated() ? (
    <Navigate to="/home" replace />
  ) : (
    <Navigate to="/login" replace />
  )
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/home" element={<Home />} />
        <Route path="/log-period" element={<LogPeriod />} />
        <Route path="/calendar" element={<CalendarView />} />
        <Route path="/settings/notifications" element={<NotificationSettings />} />
        {/* Fallback route */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}

export default App
