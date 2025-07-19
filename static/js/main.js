// Global utilities and shared functionality

// Format time helper
function formatTime(seconds) {
  const mins = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${mins}:${secs.toString().padStart(2, "0")}`
}

// Show notification helper
function showNotification(message, type = "success") {
  const notification = document.createElement("div")
  notification.className = `notification ${type}`
  notification.textContent = message

  // Style based on type
  if (type === "error") {
    notification.style.background = "#dc3545"
  } else if (type === "warning") {
    notification.style.background = "#ffc107"
    notification.style.color = "#212529"
  }

  document.body.appendChild(notification)

  // Auto remove after 3 seconds
  setTimeout(() => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification)
    }
  }, 3000)

  // Allow manual close on click
  notification.addEventListener("click", () => {
    if (notification.parentNode) {
      notification.parentNode.removeChild(notification)
    }
  })
}

// Copy to clipboard helper
function copyToClipboard(text) {
  if (navigator.clipboard) {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        showNotification("Copied to clipboard!")
      })
      .catch(() => {
        fallbackCopyToClipboard(text)
      })
  } else {
    fallbackCopyToClipboard(text)
  }
}

function fallbackCopyToClipboard(text) {
  const textArea = document.createElement("textarea")
  textArea.value = text
  textArea.style.position = "fixed"
  textArea.style.left = "-999999px"
  textArea.style.top = "-999999px"
  document.body.appendChild(textArea)
  textArea.focus()
  textArea.select()

  try {
    document.execCommand("copy")
    showNotification("Copied to clipboard!")
  } catch (err) {
    showNotification("Failed to copy to clipboard", "error")
  }

  document.body.removeChild(textArea)
}

// Debounce helper for search
function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

// Initialize common functionality when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  // Add click-to-copy functionality for room IDs
  const roomIdElements = document.querySelectorAll(".room-id")
  roomIdElements.forEach((element) => {
    element.style.cursor = "pointer"
    element.title = "Click to copy"
    element.addEventListener("click", () => {
      const roomId = element.textContent.replace("Room ID: ", "")
      copyToClipboard(roomId)
    })
  })

  // Add form validation helpers
  const forms = document.querySelectorAll("form")
  forms.forEach((form) => {
    const inputs = form.querySelectorAll("input[required]")
    inputs.forEach((input) => {
      input.addEventListener("blur", validateInput)
      input.addEventListener("input", clearValidationError)
    })
  })
})

function validateInput(event) {
  const input = event.target
  const value = input.value.trim()

  // Remove existing error styling
  input.classList.remove("error")

  // Check if required field is empty
  if (input.hasAttribute("required") && !value) {
    showInputError(input, "This field is required")
    return false
  }

  // Email validation
  if (input.type === "email" && value) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(value)) {
      showInputError(input, "Please enter a valid email address")
      return false
    }
  }

  // PIN validation (4 digits)
  if (input.name === "roomPin" || input.name === "joinPin") {
    if (value && !/^\d{4}$/.test(value)) {
      showInputError(input, "PIN must be exactly 4 digits")
      return false
    }
  }

  return true
}

function showInputError(input, message) {
  input.classList.add("error")

  // Remove existing error message
  const existingError = input.parentNode.querySelector(".input-error")
  if (existingError) {
    existingError.remove()
  }

  // Add new error message
  const errorDiv = document.createElement("div")
  errorDiv.className = "input-error"
  errorDiv.textContent = message
  errorDiv.style.color = "#dc3545"
  errorDiv.style.fontSize = "0.875rem"
  errorDiv.style.marginTop = "0.25rem"

  input.parentNode.appendChild(errorDiv)
}

function clearValidationError(event) {
  const input = event.target
  input.classList.remove("error")

  const errorDiv = input.parentNode.querySelector(".input-error")
  if (errorDiv) {
    errorDiv.remove()
  }
}

// Add error styling to CSS
const style = document.createElement("style")
style.textContent = `
    .form-group input.error {
        border-color: #dc3545 !important;
        box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
    }
    
    .input-error {
        animation: fadeIn 0.3s ease;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-5px); }
        to { opacity: 1; transform: translateY(0); }
    }
`
document.head.appendChild(style)
