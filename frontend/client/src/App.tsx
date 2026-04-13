import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { AuthWrapper } from "@/components/AuthWrapper";
import { useSessionTracker } from "@/hooks/useSessionTracker";
import Landing from "./pages/Landing";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import Therapist from "./pages/Therapist";
import History from "./pages/History";
import Profile from "./pages/Profile";
import About from "./pages/About";
import LearnMore from "./pages/LearnMore";
import NotFound from "./pages/NotFound";
import OAuthSuccess from "./pages/OAuthSuccess";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  // Initialize session tracking
  useSessionTracker();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="therapist-ui-theme">
        <TooltipProvider>
          <Toaster />
          <BrowserRouter>
            <AuthWrapper>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/auth" element={<Auth />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/therapist" element={<Therapist />} />
                <Route path="/history" element={<History />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/about" element={<About />} />
                <Route path="/learn-more" element={<LearnMore />} />
                <Route path="/auth/oauth-success" element={<OAuthSuccess />} />
                <Route path="*" element={<NotFound />} />
              </Routes>
            </AuthWrapper>
          </BrowserRouter>
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;