using System;
using System.Collections.Generic;
using UnityEngine;

namespace PolyForge
{
    [Serializable] public class ArenaEvent
    {
        public string name;public string actor;public int frame;public int round;public float time;public float value;
    }
    [DefaultExecutionOrder(-100)]
    public sealed class ArenaSession : MonoBehaviour
    {
        public PlayerController player;
        public PatrolEnemy[] enemies;
        public Vector3 playerSpawn;
        public float survivalSeconds=30;
        public int seed=42;
        public string sceneId="main";
        public string inputDigest;
        public string State {get;private set;}="RUNNING";
        public float ElapsedSeconds {get;private set;}
        public int Frame {get;private set;}
        public int Round {get;private set;}
        public readonly List<ArenaEvent> Events=new List<ArenaEvent>();
        void Start()
        {
            if(player==null || enemies==null || enemies.Length==0)throw new InvalidOperationException("Arena requires player and enemy bindings");
            Restart();Record("arena_started","arena",0);
        }
        void FixedUpdate()
        {
            Frame++;
            if(player!=null && player.Input!=null && player.Input.ConsumeRestart()){Restart();return;}
            if(State!="RUNNING")return;
            if(player.Health.Current<=0){Fail();return;}
            ElapsedSeconds+=Time.fixedDeltaTime;
            if(ElapsedSeconds>=survivalSeconds){State="WON";Record("won","player",ElapsedSeconds);}
        }
        public void Restart()
        {
            UnityEngine.Random.InitState(seed);Round++;ElapsedSeconds=0;State="RUNNING";
            player.ResetAt(playerSpawn);foreach(var enemy in enemies)enemy.ResetPatrol();
            Record("restarted","arena",Round);
        }
        public void Fail(){if(State=="RUNNING"){State="FAILED";Record("failed","player",0);}}
        public void Record(string name,string actor,float value)
        {
            if(Events.Count<20000)Events.Add(new ArenaEvent{name=name,actor=actor,value=value,frame=Frame,round=Round,time=ElapsedSeconds});
        }
    }
}
