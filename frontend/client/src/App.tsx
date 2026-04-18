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
import AdminDashboard from "./pages/AdminDashboard";
import AdminProfile from "./pages/AdminProfile";
import Therapist from "./pages/Therapist";
import History from "./pages/History";
import Profile from "./pages/Profile";
import About from "./pages/About";
import LearnMore from "./pages/LearnMore";
import NotFound from "./pages/NotFound";
import OAuthSuccess from "./pages/OAuthSuccess";
import Questionnaire from "./pages/Questionnaire";
import TherapistDashboard from "./pages/TherapistDashboard";
import TherapistPending from "./pages/TherapistPending";
import TherapistProfile from "./pages/TherapistProfile";
import TherapistMessages from "./pages/TherapistMessages";
import PatientView from "./pages/PatientView";
import MyTherapists from "./pages/MyTherapists";
import InviteAccept from "./pages/InviteAccept";
import Safety from "./pages/Safety";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
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
                <Route path="/questionnaire" element={<Questionnaire />} />
                <Route path="/auth/therapist" element={<Auth />} />
                <Route path="/auth/oauth-success" element={<OAuthSuccess />} />

                {/* Patient app */}
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/chat" element={<Therapist />} />
                <Route path="/therapist" element={<Therapist />} />
                <Route path="/history" element={<History />} />
                <Route path="/profile" element={<Profile />} />
                <Route path="/my-therapists" element={<MyTherapists />} />
                <Route path="/safety" element={<Safety />} />

                {/* Admin */}
                <Route path="/admin" element={<AdminDashboard />} />
                <Route path="/admin/profile" element={<AdminProfile />} />

                {/* Therapist portal */}
                <Route path="/therapist-portal" element={<TherapistDashboard />} />
                <Route path="/therapist-portal/clients" element={<TherapistDashboard />} />
                <Route path="/therapist-portal/pending" element={<TherapistPending />} />
                <Route path="/therapist-portal/profile" element={<TherapistProfile />} />
                <Route path="/therapist-portal/messages" element={<TherapistMessages />} />
                <Route path="/therapist-portal/patients/:id" element={<PatientView />} />

                {/* Public */}
                <Route path="/about" element={<About />} />
                <Route path="/learn-more" element={<LearnMore />} />
                <Route path="/invite/accept" element={<InviteAccept />} />

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
