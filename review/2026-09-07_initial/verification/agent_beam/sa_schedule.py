import math
Tmax, Tmin = 10.0, 0.001
steps_cfg, max_evals, pool = 500, 500, 10
effective_steps = max(steps_cfg, max_evals+1)
Tfactor = -math.log(Tmax/Tmin)
max_moves = max_evals // pool
print(f"effective_steps={effective_steps}, max moves before budget exhaustion={max_moves}")
for step in [1,10,25,50,51]:
    T = Tmax*math.exp(Tfactor*step/effective_steps)
    print(f"  step={step:3d}: T={T:.4f}; accept prob for dE=0.05: {math.exp(-0.05/T):.4f}, dE=0.25: {math.exp(-0.25/T):.4f}, dE=1.0: {math.exp(-1.0/T):.4f}")
# what T would be reached if the schedule length matched the actual move count
print("If steps were set to max_moves (=50): T at last step =", Tmax*math.exp(Tfactor*50/50))
