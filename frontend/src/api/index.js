import axios from "axios"

// 🔥 CREATE AXIOS INSTANCE
const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 10000
})

// 🔐 HARDCODE TOKEN (TEMP FOR DEMO - REMOVE LATER)
const HARDCODED_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyIiwiZW1haWwiOiJrYXJ0aGlrZUA4NCIsInR5cGUiOiJhY2Nlc3MiLCJleHAiOjE3NzUyMDc0MzQsImlhdCI6MTc3NTIwNTYzNH0.H9cKZna4sLzZkTYfSgtnkU8AoAbXy5qmqzW6aS2m29Q"

// 🔹 REQUEST INTERCEPTOR (ATTACH TOKEN)
API.interceptors.request.use(
  (config) => {
    // Try localStorage first
    let token = localStorage.getItem("access_token")

    // 🔥 Proper fallback
    if (!token) {
      token = HARDCODED_TOKEN
    }

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    console.log("➡️ API Request:", config.url)
    return config
  },
  (error) => {
    console.error("❌ Request Error:", error)
    return Promise.reject(error)
  }
)

// 🔹 RESPONSE INTERCEPTOR (DEBUG + ERROR HANDLING)
API.interceptors.response.use(
  (response) => {
    API.interceptors.request.use(
  (config) => {
    // Try localStorage first
    let token = localStorage.getItem("access_token")

    // 🔥 Proper fallback
    if (!token) {
      token = HARDCODED_TOKEN
    }

    // 🔥 ADD THIS LINE HERE
    console.log("🔥 TOKEN BEING USED:", token)

    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }

    console.log("➡️ API Request:", config.url)
    return config
  },
  (error) => {
    console.error("❌ Request Error:", error)
    return Promise.reject(error)
  }
)
    console.log("✅ API Response:", response.config.url, response.data)
    return response
  },
  (error) => {
    console.error("❌ API Error:", error.response?.data || error.message)

    // 🔥 Handle unauthorized
    if (error.response?.status === 401) {
      console.warn("⚠️ Unauthorized - clearing token")
      localStorage.removeItem("access_token")
    }

    return Promise.reject(error)
  }
)

// 🔹 Dashboard API
export const dashboardAPI = async () => {
  try {
    const res = await API.get("/dashboard/data")
    return res.data
  } catch (err) {
    console.error("Dashboard API failed:", err)
    throw err
  }
}

// 🔹 Claims API
export const claimsAPI = async (trigger_type) => {
  try {
    const res = await API.post("/claims/trigger", { trigger_type })
    return res.data
  } catch (err) {
    console.error("Claims API failed:", err)
    throw err
  }
}

// 🔹 Environment API
export const envAPI = async () => {
  try {
    const res = await API.get("/environment")
    return res.data
  } catch (err) {
    console.error("Environment API failed:", err)
    throw err
  }
}

// 🔹 Auth helpers
export const clearAuthTokens = () => {
  localStorage.removeItem("access_token")
}

// 🔹 Get current token/user
export const getCurrentUser = () => {
  return localStorage.getItem("access_token") || HARDCODED_TOKEN
}