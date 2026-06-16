import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

// StrictMode tắt CHỦ Ý: ở dev nó double-invoke mọi effect → tạo 2 session (2 Docker
// container), 2 interval poll, 2 WebSocket → request storm + lag khi test. App này có
// side-effect nặng (mở container, WS) không nên chạy 2 lần. Production vốn không
// double-invoke nên hành vi không đổi khi build.
ReactDOM.createRoot(document.getElementById('root')!).render(<App />)
