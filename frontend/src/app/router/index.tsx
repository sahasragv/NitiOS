import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AppLayout } from '@/components/layout/app-layout'
import { HomePage } from '@/modules/home/pages/home-page'
const router = createBrowserRouter([{ element: <AppLayout />, children: [{ index: true, element: <HomePage /> }] }])
export function AppRouter() { return <RouterProvider router={router} /> }
