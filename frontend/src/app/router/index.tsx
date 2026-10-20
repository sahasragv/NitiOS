import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AuthGate } from '@/modules/auth/components/auth-gate'
import { ChatPage } from '@/modules/chat/pages/chat-page'
const router = createBrowserRouter([
  { path: '/', element: <AuthGate>{(user, notice) => <ChatPage key={user.id} user={user} notice={notice} />}</AuthGate> },
])
export function AppRouter() { return <RouterProvider router={router} /> }
