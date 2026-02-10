import React from 'react';

const BackgroundDecor: React.FC = () => {
    return (
        <div className="fixed inset-0 overflow-hidden -z-10 pointer-events-none">
            <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-primary/30 rounded-full mix-blend-multiply filter blur-3xl animate-blob"></div>
            <div className="absolute top-[-5%] right-[0%] w-[500px] h-[500px] bg-secondary/30 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-2000"></div>
            <div className="absolute bottom-[-10%] left-[20%] w-[600px] h-[600px] bg-accent/30 rounded-full mix-blend-multiply filter blur-3xl animate-blob animation-delay-4000"></div>
        </div>
    );
};

export default BackgroundDecor;
