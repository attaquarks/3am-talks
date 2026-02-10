import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Wind, Heart, Shield, Sparkles, ArrowRight, MessageSquare, TrendingUp, Clock } from "lucide-react";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-ai-therapist.png";
import BackgroundDecor from "@/components/auth/BackgroundDecor";

export default function Landing() {
  return (
    <div className="min-h-screen relative flex flex-col bg-gradient-to-br from-primary/10 via-background to-secondary/10 selection:bg-primary/30 overflow-x-hidden">
      <BackgroundDecor />
      {/* Header */}
      <header className="border-b bg-background/40 backdrop-blur-xl sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4 group cursor-pointer" onClick={() => window.location.href = '/'}>
            <div className="relative w-10 h-10 flex items-center justify-center">
              <Wind className="absolute text-primary/40 animate-pulse" size={32} strokeWidth={1.5} />
              <Sparkles className="absolute text-accent/60 -top-1 -right-1 animate-bounce" size={16} />
            </div>
            <span className="text-2xl font-light tracking-[0.25em] uppercase">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent">Ella AI</span>
            </span>
          </div>
          <div className="flex gap-2">
            <Button asChild variant="outline">
              <Link to="/auth">Sign In</Link>
            </Button>
            <Button asChild>
              <Link to="/auth">Get Started</Link>
            </Button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-6xl">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <div className="space-y-4">
                <div className="flex items-center gap-2 text-primary">
                  <Sparkles className="h-5 w-5" />
                  <span className="text-sm font-medium">AI-Powered Mental Wellness</span>
                </div>
                <h1 className="text-5xl md:text-7xl font-extralight leading-tight tracking-tight uppercase">
                  Your Personal{" "}
                  <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-accent font-black tracking-tighter italic">
                    Ella AI
                  </span>
                </h1>
                <p className="text-xl text-muted-foreground max-w-lg">
                  Get compassionate support, track your mental health journey, and build better habits with our AI-powered therapy assistant available 24/7.
                </p>
              </div>

              <div className="flex flex-col sm:flex-row gap-4">
                <Button asChild size="lg" className="shadow-lg">
                  <Link to="/auth" className="flex items-center gap-2">
                    Start Your Journey <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
                <Button asChild variant="outline" size="lg">
                  <Link to="/learn-more">Learn More</Link>
                </Button>
              </div>

              <div className="flex items-center gap-8 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4 text-green-500" />
                  <span>100% Private & Secure</span>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-blue-500" />
                  <span>Available 24/7</span>
                </div>
              </div>
            </div>

            <div className="relative">
              <div className="relative z-10">
                <img
                  src={heroImage}
                  alt="AI Therapist Assistant"
                  className="w-full h-auto rounded-2xl shadow-2xl"
                />
              </div>
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-secondary/20 rounded-2xl blur-3xl -z-10 transform scale-105"></div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 bg-muted/30">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center space-y-4 mb-16">
            <h2 className="text-3xl md:text-4xl font-bold">
              Everything you need for mental wellness
            </h2>
            <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
              Our comprehensive platform provides tools and insights to support your mental health journey.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            <Card className="relative overflow-hidden border-0 shadow-lg">
              <CardHeader className="space-y-4">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <MessageSquare className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>AI Conversations</CardTitle>
                <CardDescription>
                  Have meaningful conversations with our empathetic AI therapist that understands your emotions and provides personalized support.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="relative overflow-hidden border-0 shadow-lg">
              <CardHeader className="space-y-4">
                <div className="w-12 h-12 rounded-lg bg-secondary/10 flex items-center justify-center">
                  <TrendingUp className="h-6 w-6 text-secondary" />
                </div>
                <CardTitle>Mood Tracking</CardTitle>
                <CardDescription>
                  Monitor your emotional patterns and track your progress with beautiful visualizations and insightful analytics.
                </CardDescription>
              </CardHeader>
            </Card>

            <Card className="relative overflow-hidden border-0 shadow-lg">
              <CardHeader className="space-y-4">
                <div className="w-12 h-12 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Shield className="h-6 w-6 text-accent" />
                </div>
                <CardTitle>Privacy First</CardTitle>
                <CardDescription>
                  Your conversations and data are completely private and secure. We use end-to-end encryption to protect your information.
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4">
        <div className="container mx-auto max-w-4xl text-center">
          <Card className="border-0 shadow-xl bg-gradient-to-br from-primary/5 to-secondary/5">
            <CardHeader className="space-y-6 py-12">
              <div className="flex justify-center">
                <div className="flex items-center gap-2">
                  <Heart className="h-8 w-8 text-primary" />
                  <Wind className="h-8 w-8 text-secondary" />
                  <Sparkles className="h-8 w-8 text-accent" />
                </div>
              </div>
              <CardTitle className="text-3xl md:text-4xl">
                Ready to start your mental wellness journey?
              </CardTitle>
              <CardDescription className="text-lg max-w-2xl mx-auto">
                Join thousands of users who have found comfort, support, and growth with our AI therapy assistant.
                Your mental health matters, and we're here to help you thrive.
              </CardDescription>
              <div className="pt-4">
                <Button asChild size="lg" className="shadow-lg">
                  <Link to="/auth" className="flex items-center gap-2">
                    Get Started Free <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardHeader>
          </Card>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t py-8 px-4">
        <div className="container mx-auto text-center text-muted-foreground">
          <p>&copy; 2024 AI Therapy Assistant. Your mental wellness companion.</p>
        </div>
      </footer>
    </div>
  );
}