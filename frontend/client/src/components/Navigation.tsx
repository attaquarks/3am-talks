import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  Moon, Sun, MessageCircle, Calendar, User, Home, Info, Wind, Sparkles,
  Shield, ShieldCheck, Stethoscope, Users, Inbox, Briefcase, HeartHandshake, LogOut, ShieldAlert,
} from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { cn } from "@/lib/utils";

type NavItem = { path: string; icon: typeof Home; label: string };

function useNavItems(): NavItem[] {
  const { user } = useAuth();
  const role = user?.role ?? 'patient';

  if (role === 'admin') {
    return [
      { path: "/admin", icon: Shield, label: "Admin" },
      { path: "/admin/profile", icon: ShieldCheck, label: "Admin Profile" },
    ];
  }
  if (role === 'therapist') {
    return [
      { path: "/therapist-portal", icon: Briefcase, label: "Portal" },
      { path: "/therapist-portal/clients", icon: Users, label: "Clients" },
      { path: "/therapist-portal/messages", icon: Inbox, label: "Messages" },
      { path: "/therapist-portal/profile", icon: Stethoscope, label: "Profile" },
    ];
  }
  return [
    { path: "/dashboard", icon: Home, label: "Dashboard" },
    { path: "/chat", icon: MessageCircle, label: "ELLA" },
    { path: "/my-therapists", icon: HeartHandshake, label: "Therapists" },
    { path: "/safety", icon: ShieldAlert, label: "Safety" },
    { path: "/history", icon: Calendar, label: "History" },
    { path: "/profile", icon: User, label: "Profile" },
  ];
}

export function Navigation() {
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();
  const currentPath = location.pathname;
  const navItems = useNavItems();
  const { user, signOut } = useAuth();
  const { toast } = useToast();

  const isActive = (path: string) =>
    currentPath === path || (path !== '/' && currentPath.startsWith(path + '/'));

  const handleLogout = async () => {
    try {
      await signOut();
      toast({ title: "Signed out" });
      navigate('/');
    } catch (err: any) {
      toast({ title: "Sign out failed", description: err?.message ?? "Please try again", variant: "destructive" });
    }
  };

  return (
    <nav className="w-full sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-md">
      <div className="container mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link to="/" className="flex items-center space-x-3 group">
            <div className="relative w-8 h-8 flex items-center justify-center">
              <Wind className="absolute text-primary/40 group-hover:rotate-12 transition-all" size={24} strokeWidth={1.5} />
              <Sparkles className="absolute text-accent/60 -top-0.5 -right-0.5 animate-pulse" size={12} />
            </div>
            <span className="text-xl font-light tracking-[0.2em] uppercase">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
            </span>
          </Link>

          <div className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200",
                  isActive(item.path)
                    ? "bg-primary text-primary-foreground shadow-soft-sm"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent"
                )}
              >
                <item.icon className="h-4 w-4" />
                <span className="text-sm font-medium">{item.label}</span>
              </Link>
            ))}
          </div>

          <div className="flex items-center space-x-2">
            <Button variant="ghost" size="icon" asChild className="rounded-lg">
              <Link to="/about">
                <Info className="h-4 w-4" />
                <span className="sr-only">About Us</span>
              </Link>
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              className="rounded-lg"
            >
              <Sun className="h-4 w-4 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
              <Moon className="absolute h-4 w-4 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
              <span className="sr-only">Toggle theme</span>
            </Button>

            {user && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleLogout}
                className="rounded-lg text-muted-foreground hover:text-destructive"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
                <span className="sr-only">Sign out</span>
              </Button>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

export function MobileNavigation() {
  const location = useLocation();
  const currentPath = location.pathname;
  const navItems = useNavItems();

  const isActive = (path: string) =>
    currentPath === path || (path !== '/' && currentPath.startsWith(path + '/'));

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-background/90 backdrop-blur-md border-t border-border md:hidden">
      <div className="grid py-2" style={{ gridTemplateColumns: `repeat(${navItems.length}, minmax(0, 1fr))` }}>
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={cn(
              "flex flex-col items-center justify-center py-2 px-3 transition-all duration-200",
              isActive(item.path)
                ? "text-primary"
                : "text-muted-foreground"
            )}
          >
            <item.icon className={cn("h-5 w-5 mb-1", isActive(item.path) && "animate-scale-in")} />
            <span className="text-xs font-medium">{item.label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
