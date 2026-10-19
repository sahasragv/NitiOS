import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { ChatPage } from '@/modules/chat/pages/chat-page'
const router = createBrowserRouter([{ path: '/', element: <ChatPage /> }])
export function AppRouter() { return <RouterProvider router={router} /> }
