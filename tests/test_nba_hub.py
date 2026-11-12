from datetime import datetime, timezone
import pytest
from nba_hub import standings_data, schedule_data, team_details


def test_standings_use_provider_seed_not_feed_order():
    groups=[]
    for conf in ['East','West']:
        entries=[{'team':{'id':str(i),'displayName':f'Team {i}'},'stats':[{'name':'playoffSeed','value':16-i},{'name':'wins','value':i}]} for i in range(1,16)]
        groups.append({'name':conf,'standings':{'entries':entries}})
    result=standings_data({'children':groups})
    assert result['conferences'][0]['teams'][0]['rank']==1
    assert result['conferences'][0]['teams'][0]['id']=='15'
    assert result['conferences'][0]['teams'][0]['win_percent'] is None
    with pytest.raises(ValueError): standings_data({'children':groups[:1]})


def test_schedule_uses_competition_status_rome_dates_and_score_objects():
    def event(id,date,state):
        return {'id':id,'date':date,'competitions':[{'timeValid':False,'status':{'type':{'state':state}},'competitors':[{'homeAway':'home','team':{'displayName':'Home'},'score':{'displayValue':'110'}},{'homeAway':'away','team':{'displayName':'Away'},'score':{'displayValue':'100'}}]}]}
    result=schedule_data({'team':{'id':'2'},'events':[event('1','2026-11-11T23:30Z','post'),event('2','2026-11-12T23:30Z','pre'),event('3','2026-11-10T23:30Z','pre')]},datetime(2026,11,12,tzinfo=timezone.utc))
    assert len(result['upcoming'])==1
    assert result['upcoming'][0]['calendar_date']=='2026-11-13'
    assert result['recent'][0]['home_score']=='110'
    assert result['upcoming'][0]['time_valid'] is False
    assert result['odds_api_calls']==0


def test_unknown_team_rejected_before_upstream():
    with pytest.raises(Exception) as exc: team_details('999999')
    assert exc.value.status_code==404
