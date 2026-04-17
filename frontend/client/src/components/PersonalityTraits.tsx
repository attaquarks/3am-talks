import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Users,
  Activity,
  Heart,
  Target,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  ArrowRight
} from "lucide-react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";

interface Profile {
  id: string;
  user_id: string;
  name: string;
  mood_preference: string;
  emergency_contact?: string;
  deleted?: boolean;
  created_at: string;
  updated_at: string;
  extroversion: number;
  neuroticism: number;
  agreeableness: number;
  conscientiousness: number;
  openness: number;
  total_text_analyzed: number;
  personality_updated_at: string | null;
}

interface PersonalityTraitsProps {
  profile: Profile | null;
  loading?: boolean;
}

interface TraitConfig {
  key: keyof Pick<Profile, 'extroversion' | 'neuroticism' | 'agreeableness' | 'conscientiousness' | 'openness'>;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  lowLabel: string;
  highLabel: string;
}

const traitConfigs: TraitConfig[] = [
  {
    key: 'openness',
    label: 'Openness',
    description: 'Curiosity and openness to new experiences',
    icon: <Sparkles className="w-4 h-4" />,
    color: 'purple',
    lowLabel: 'Practical',
    highLabel: 'Curious'
  },
  {
    key: 'conscientiousness',
    label: 'Conscientiousness',
    description: 'Organization and dependability',
    icon: <Target className="w-4 h-4" />,
    color: 'green',
    lowLabel: 'Flexible',
    highLabel: 'Organized'
  },
  {
    key: 'extroversion',
    label: 'Extroversion',
    description: 'Social energy and assertiveness',
    icon: <Users className="w-4 h-4" />,
    color: 'blue',
    lowLabel: 'Reserved',
    highLabel: 'Outgoing'
  },
  {
    key: 'agreeableness',
    label: 'Agreeableness',
    description: 'Cooperation and compassion',
    icon: <Heart className="w-4 h-4" />,
    color: 'pink',
    lowLabel: 'Independent',
    highLabel: 'Compassionate'
  },
  {
    key: 'neuroticism',
    label: 'Neuroticism',
    description: 'Emotional sensitivity and stress response',
    icon: <Activity className="w-4 h-4" />,
    color: 'orange',
    lowLabel: 'Resilient',
    highLabel: 'Sensitive'
  }
];

const colorClasses: Record<string, { bg: string; text: string; progress: string }> = {
  purple: { bg: 'bg-purple-100', text: 'text-purple-600', progress: 'bg-purple-500' },
  green: { bg: 'bg-green-100', text: 'text-green-600', progress: 'bg-green-500' },
  blue: { bg: 'bg-blue-100', text: 'text-blue-600', progress: 'bg-blue-500' },
  pink: { bg: 'bg-pink-100', text: 'text-pink-600', progress: 'bg-pink-500' },
  orange: { bg: 'bg-orange-100', text: 'text-orange-600', progress: 'bg-orange-500' }
};

function getTrendIcon(value: number, prevValue?: number) {
  if (prevValue === undefined || prevValue === null) return null;
  const diff = value - prevValue;
  if (Math.abs(diff) < 0.05) return <Minus className="w-3 h-3 text-muted-foreground" />;
  if (diff > 0) return <TrendingUp className="w-3 h-3 text-green-500" />;
  return <TrendingDown className="w-3 h-3 text-red-500" />;
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return 'Never';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  return date.toLocaleDateString();
}

function getTraitInterpretation(key: string, value: number): string {
  if (key === 'neuroticism') {
    if (value < 0.35) return 'Tends to stay calm under pressure and handles stress well.';
    if (value > 0.65) return 'May experience emotions intensely and benefit from stress management.';
    return 'Generally balanced emotional responses with room for growth.';
  }
  if (key === 'openness') {
    if (value < 0.35) return 'Prefers familiar routines and practical approaches.';
    if (value > 0.65) return 'Highly imaginative and eager to explore new ideas.';
    return 'Balanced between creativity and practicality.';
  }
  if (key === 'conscientiousness') {
    if (value < 0.35) return 'Flexible and spontaneous, may prefer go-with-the-flow approaches.';
    if (value > 0.65) return 'Highly organized and goal-oriented.';
    return 'Balanced approach to structure and flexibility.';
  }
  if (key === 'extroversion') {
    if (value < 0.35) return 'Prefers quieter environments and deeper one-on-one connections.';
    if (value > 0.65) return 'Draws energy from social interactions and group settings.';
    return 'Comfortable in both social and solitary settings.';
  }
  if (key === 'agreeableness') {
    if (value < 0.35) return 'Independent thinker who values direct communication.';
    if (value > 0.65) return 'Highly empathetic and values harmony in relationships.';
    return 'Balanced approach to cooperation and independence.';
  }
  return '';
}

export default function PersonalityTraits({ profile, loading }: PersonalityTraitsProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="space-y-2">
            <div className="flex justify-between">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-12" />
            </div>
            <Skeleton className="h-2 w-full" />
          </div>
        ))}
      </div>
    );
  }

  // Default values for new users
  const traits = {
    extroversion: profile?.extroversion ?? 0,
    neuroticism: profile?.neuroticism ?? 0,
    agreeableness: profile?.agreeableness ?? 0,
    conscientiousness: profile?.conscientiousness ?? 0,
    openness: profile?.openness ?? 0
  };

  const hasPersonalityData = profile && profile.total_text_analyzed > 0;

  return (
    <div className="space-y-6">
      {/* Header with last update */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {hasPersonalityData
            ? `${profile?.total_text_analyzed?.toLocaleString() || 0} characters analyzed`
            : 'Start chatting to discover your personality'
          }
        </span>
        {hasPersonalityData && (
          <span className="flex items-center gap-1">
            Updated: {formatDate(profile?.personality_updated_at)}
          </span>
        )}
      </div>

      {/* Traits List */}
      <div className="space-y-4">
        {traitConfigs.map((config) => {
          const value = traits[config.key];
          const percentage = Math.round(value * 100);
          const colors = colorClasses[config.color];
          const interpretation = getTraitInterpretation(config.key, value);

          return (
            <div key={config.key} className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-md ${colors.bg} ${colors.text}`}>
                    {config.icon}
                  </div>
                  <div>
                    <span className="font-medium text-foreground">{config.label}</span>
                    <p className="text-xs text-muted-foreground">{config.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold" title={`Score: ${percentage}%`}>
                    {percentage}%
                  </span>
                </div>
              </div>

              <div className="relative">
                <Progress
                  value={percentage}
                  className="h-2"
                />
                <div
                  className={`absolute top-0 left-0 h-2 rounded-full ${colors.progress} transition-all duration-500`}
                  style={{ width: `${percentage}%` }}
                />
              </div>

              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{config.lowLabel}</span>
                <span>{config.highLabel}</span>
              </div>

              {hasPersonalityData && (
                <p className="text-xs text-muted-foreground italic">
                  {interpretation}
                </p>
              )}
            </div>
          );
        })}
      </div>

      {/* Personality Summary Card */}
      {hasPersonalityData && (
        <Card className="bg-gradient-to-r from-primary/5 to-secondary/5 border-primary/20">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-primary/10">
                <Sparkles className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h4 className="font-semibold text-foreground mb-1">Your Personality Profile</h4>
                <p className="text-sm text-muted-foreground">
                  Based on your conversations, ELLA adapts her therapeutic approach to match your unique personality.
                  Your traits evolve as you continue your mental health journey.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Empty State / CTA */}
      {!hasPersonalityData && (
        <motion.div 
          initial={{ opacity: 0, y: 10 }} 
          animate={{ opacity: 1, y: 0 }}
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary/10 via-background to-secondary/10 border border-primary/20 p-6 text-center shadow-lg"
        >
          <div className="absolute top-0 right-0 p-4 opacity-50">
             <motion.div
                 animate={{ scale: [1, 1.2, 1], opacity: [0.3, 0.6, 0.3] }}
                 transition={{ duration: 4, repeat: Infinity }}
                 className="w-24 h-24 bg-primary/30 rounded-full blur-2xl"
             />
          </div>
          <div className="relative z-10">
            <div className="w-16 h-16 bg-white/50 dark:bg-black/50 backdrop-blur-md rounded-full flex items-center justify-center mx-auto mb-4 border border-white/20 shadow-xl">
              <Activity className="w-8 h-8 text-primary" />
            </div>
            <h4 className="text-xl font-bold tracking-tight text-foreground mb-2">Uncover Your Psyche</h4>
            <p className="text-sm text-muted-foreground mb-6 max-w-xs mx-auto">
              These deeper questions help our model understand your unique traits and adapt specifically to you. 
              <br/><br/>
              <motion.span 
                animate={{ opacity: [0.5, 1, 0.5] }} 
                transition={{ duration: 2, repeat: Infinity }}
                className="font-semibold text-primary inline-block"
              >
                Let ELLA discover the real you.
              </motion.span>
            </p>
            
            <Link to="/questionnaire">
              <motion.button 
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="bg-primary hover:bg-primary/90 text-primary-foreground font-bold py-3 px-6 rounded-xl shadow-xl shadow-primary/20 transition-all flex items-center justify-center gap-2 mx-auto"
              >
                <Sparkles className="w-4 h-4" />
                Assess Your Personality
                <ArrowRight className="w-4 h-4 ml-1" />
              </motion.button>
            </Link>
          </div>
        </motion.div>
      )}
    </div>
  );
}