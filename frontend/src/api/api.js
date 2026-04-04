import axios from "axios"

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
  timeout: 10000
})

// 🔐 Attach token
API.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token")

  // 🔥 DEBUG LOG (helps during auth issues)
  console.log("🔐 Attaching token:", token ? "YES" : "NO")

  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  // 🔥 ENSURE HEADERS OBJECT EXISTS (bug prevention)
  if (!config.headers) {
    config.headers = {}
  }

  // 🔥 FORCE JSON HEADERS (important for FastAPI)
  if (!(config.data instanceof URLSearchParams)) {
    config.headers["Content-Type"] = "application/json"
  }

 // 🔥 EXTRA DEBUG
console.log("➡️ Request:", config.method?.toUpperCase(), config.url, config.data || "")

return config
}, (error) => {
  console.error("❌ Request error:", error)
  return Promise.reject(error)
})


// 🔥 RESPONSE INTERCEPTOR (VERY IMPORTANT)
API.interceptors.response.use(
  (response) => {
    // 🔥 DEBUG SUCCESS
    console.log("✅ Response:", response.config.url, response.data)

    // 🔥 AUTO REFRESH TOKEN SUPPORT (future ready)
    if (response.data?.access_token) {
      console.log("🔄 Updating access token from response")
      localStorage.setItem("access_token", response.data.access_token)
    }

    return response
  },
  async (error) => {

    console.error("❌ API Error:", error.response?.data || error.message)

    const originalRequest = error.config

    // 🔥 PREVENT CRASH IF NO RESPONSE
    if (!error.response) {
      console.error("🚫 Network error or server down")
      return Promise.reject(error)
    }

    // 🔥 SAFE 401 HANDLING (FIXED — NO LOGIN LOOP)
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url.includes("/auth/login")
    ) {
      console.warn("⚠️ Unauthorized request detected")

      originalRequest._retry = true

      alert("Session expired. Please login again.")

      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      localStorage.removeItem("user")

      window.location.href = "/login"

      return Promise.reject(error) // 🔥 STOP EXECUTION
    }

    // 🔥 OPTIONAL: future refresh token logic placeholder
    const refreshToken = localStorage.getItem("refresh_token")

    if (refreshToken) {
      console.log("🔄 Attempting silent refresh (future feature)")
      // (you can implement refresh endpoint later)
    }

    // 🔥 OLD BLOCK (kept but SAFELY DISABLED)
    if (false) {
      alert("Session expired. Please login again.")
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      localStorage.removeItem("user")
      window.location.href = "/login"
    }

    // 🔥 EXTRA DEBUG
    console.error("❌ Full error object:", error)

    return Promise.reject(error)
  }
)


// 🔹 Dashboard API
export const dashboardAPI = async (config = {}) => {
  try {
    console.log("📊 Fetching dashboard...")

    const res = await API.get("/dashboard/data", config)

    // 🔥 SAFETY CHECK
    if (!res.data) {
      throw new Error("Empty dashboard response")
    }

    return res.data
  } catch (err) {
    console.error("Dashboard API failed:", err)
    throw err
  }
}


// 🔹 Claims API
export const claimsAPI = async (trigger_type) => {
  try {
    console.log("⚡ Triggering claim:", trigger_type)

    // 🔥 CRITICAL FIX — ensure STRING
    let safeTrigger =
      typeof trigger_type === "string"
        ? trigger_type
        : trigger_type?.type || "traffic"

    console.log("✅ Final trigger used:", safeTrigger)

    const res = await API.post("/claims/trigger", {
      trigger_type: safeTrigger
    })

    console.log("✅ Claim response:", res.data)

    return res.data

  } catch (err) {
    console.error("❌ Claim API error:", err.response?.data || err.message)

    alert(err.response?.data?.detail || "Claim failed. Check backend.")

    throw err
  }
}


// 🔹 Environment API
export const envAPI = async () => {
  try {
    const res = await API.get("/environment")

    if (!res.data) {
      console.warn("⚠️ Empty environment response")
    }

    return res.data
  } catch (err) {
    console.error("Env API failed:", err)
    throw err
  }
}


// 🔥 REGISTER API
export const registerAPI = async (userData) => {
  try {
    console.log("📝 Registering user:", userData)

    const res = await API.post("/auth/register", {
      name: userData.name,
      email: userData.email,
      password: userData.password,
      city: userData.city,
      vehicle_type: userData.vehicle_type,
      declared_weekly_income: Number(userData.declared_weekly_income)
    })

    console.log("✅ Registration success:", res.data)

    if (res.data.access_token) {
      localStorage.setItem("access_token", res.data.access_token)
    }

    return res.data

  } catch (err) {
    console.error("❌ Register API error:", err.response?.data || err.message)

    alert(err.response?.data?.detail || "Registration failed")

    throw err
  }
}


// 🔥 LOGIN API
export const loginAPI = async (email, password) => {
  try {
    console.log("🔑 Logging in:", email)

    const res = await API.post("/auth/login", {
      email,
      password
    })

    console.log("✅ Login success:", res.data)

    if (res.data.access_token) {
      localStorage.setItem("access_token", res.data.access_token)
    }

    if (res.data.refresh_token) {
      localStorage.setItem("refresh_token", res.data.refresh_token)
    }

    localStorage.setItem("user", JSON.stringify(res.data))

    return res.data

  } catch (err) {
    console.error("❌ Login failed:", err.response?.data || err.message)

    alert(err.response?.data?.detail || "Login failed")

    throw err
  }
}


// 🔹 CLEAR TOKEN
export const clearAuthTokens = () => {
  console.log("🧹 Clearing auth tokens")
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
  localStorage.removeItem("user")
}


// 🔹 GET CURRENT USER
export const getCurrentUser = () => {
  const token = localStorage.getItem("access_token")

  if (!token) return null

  try {
    const payload = JSON.parse(atob(token.split('.')[1]))

    return {
      id: payload.sub,
      email: payload.email,
      name: payload.email?.split("@")[0]
    }
  } catch (err) {
    console.error("❌ Token decode failed:", err)
    return null
  }
}


// 🔥 AUTH CHECK
export const isAuthenticated = () => {
  const token = localStorage.getItem("access_token")
  return !!token
}


// 🔥 SAFE WRAPPER
export const safeAPICall = async (apiFunc, ...args) => {
  try {
    return await apiFunc(...args)
  } catch (err) {
    console.error("❌ Safe API wrapper caught error:", err)
    return null
  }
}

export default API