from flask import (
    abort,
    request,
    render_template,
    redirect,
    jsonify,
    Blueprint,
    url_for,
    Response,
    session,
    send_file
)

import json
import io
import datetime
import csv

from CTFd.models import db, Challenges, Teams, Solves, Fails
from CTFd.utils.decorators import (
    authed_only,
    admins_only,
    require_verified_emails
)
from CTFd.plugins import register_plugin_assets_directory, bypass_csrf_protection
from CTFd.utils.plugins import register_script
from CTFd.utils.user import is_admin, authed, is_verified
from CTFd.utils.user import get_current_team

from sqlalchemy.sql import and_

class ChallengeFeedbackQuestions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chalid = db.Column(db.Integer, db.ForeignKey('challenges.id'))
    question = db.Column(db.String(100), nullable=False)
    inputtype = db.Column(db.Integer)
    extraarg1 = db.Column(db.String(100))
    extraarg2 = db.Column(db.String(100))

    def __init__(self, chalid, question, inputtype, extraarg1, extraarg2):
        self.chalid = chalid
        self.question = question
        self.inputtype = inputtype
        self.extraarg1 = extraarg1
        self.extraarg2 = extraarg2

class ChallengeFeedbackAnswers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    questionid = db.Column(db.Integer, db.ForeignKey('challenge_feedback_questions.id'))
    teamid = db.Column(db.Integer, db.ForeignKey('teams.id'))
    answer = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def __init__(self, questionid, teamid, answer):
        self.questionid = questionid
        self.teamid = teamid
        self.answer = answer

def load(app):
    app.db.create_all()

    challenge_feedback = Blueprint('challenge_feedback', __name__, template_folder='templates')
    challenge_feedback_static = Blueprint('challenge_feedback_static', __name__, static_folder='static')
    app.register_blueprint(challenge_feedback)
    app.register_blueprint(challenge_feedback_static, url_prefix='/challenge-feedback')

    register_plugin_assets_directory(app, base_path="/plugins/ctfd-challenge-feedback/static/")
    register_script("/plugins/ctfd-challenge-feedback/static/challenge-feedback-chal-window.js")

    @app.route('/admin/plugins/challenge-feedback', methods=['GET'])
    @admins_only
    def challenge_feedback_config_view():
        challenges = Challenges.query.all()
        return render_template('challenge-feedback-config.html', challenges=challenges)


    @app.route('/admin/chal/<int:chalid>/feedbacks', methods=['GET'])
    @admins_only
    def admin_chal_feedbacks(chalid):
        feedbacks = []
        for feedback in ChallengeFeedbackQuestions.query.filter_by(chalid=chalid).all():
            feedbacks.append({
                'id': feedback.id, 
                'question': feedback.question, 
                'type': feedback.inputtype,
                'extraarg1' : feedback.extraarg1,
                'extraarg2' : feedback.extraarg2,
            })
        data = {}
        data['feedbacks'] = feedbacks
        return jsonify(data)

    @app.route('/chal/<int:chalid>/feedbacks', methods=['GET'])
    @authed_only
    def chal_feedbacks(chalid):
        team = get_current_team()
        teamid = team.id
        # Get solved challenge ids
        solves = []
        if authed():
            solves = Solves.query\
                .join(Teams, Solves.team_id == Teams.id)\
                .filter(Solves.team_id == teamid)\
                .all()
        solve_ids = []
        for solve in solves:
            solve_ids.append(solve.challenge_id)

        # Return nothing if challenge is not solved
        if chalid not in solve_ids:
            return jsonify([])

        # Otherwise, return the feedback questions
        feedbacks = []
        for feedback in ChallengeFeedbackQuestions.query.filter_by(chalid=chalid).all():
            answer_entry = ChallengeFeedbackAnswers.query.filter(and_(
                ChallengeFeedbackAnswers.questionid==feedback.id,
                ChallengeFeedbackAnswers.teamid==teamid
            )).first()
            answer = ""
            if answer_entry is not None:
                answer = answer_entry.answer
            feedbacks.append({
                'id': feedback.id,
                'question': feedback.question,
                'type': feedback.inputtype,
                'extraarg1' : feedback.extraarg1,
                'extraarg2' : feedback.extraarg2,
                'answer': answer,
            })
        data = {}
        data['feedbacks'] = feedbacks
        return jsonify(data)

    @app.route('/chal/<int:chalid>/feedbacks/answer', methods=['POST'])
    @authed_only
    def chal_feedback_answer(chalid):
        team = get_current_team()
        teamid = team.id
        success_msg = "Thank you for your feedback"

        # Get solved challenge ids
        solves = []
        if authed():
            team = get_current_team()
            solves = Solves.query\
                .join(Teams, Solves.team_id == Teams.id)\
                .filter(Solves.team_id == team.id)\
                .all()
        solve_ids = []
        for solve in solves:
            solve_ids.append(solve.challenge_id)

        # Get feedback ids for this challenge
        feedback_ids = []
        for feedback in ChallengeFeedbackQuestions.query.filter_by(chalid=chalid).all():
            feedback_ids.append(feedback.id)

        if (authed() and chalid in solve_ids):

            for name, value in request.form.items():
                name_tokens = name.split("-")
                if name_tokens[0] == "feedback":
                    feedbackid = int(name_tokens[1])
                    if feedbackid not in feedback_ids:
                        return jsonify({
                            'status': 1,
                            'message': "Error: Invalid feedback ID"
                        })

                    existing_feedback = ChallengeFeedbackAnswers.query.filter(and_(
                        ChallengeFeedbackAnswers.questionid==feedbackid, 
                        ChallengeFeedbackAnswers.teamid==teamid
                    )).first()
                    if existing_feedback is not None:
                        db.session.delete(existing_feedback)
                        success_msg = "Your feedback has been updated"

                    feedback_answer = ChallengeFeedbackAnswers(feedbackid, teamid, value)
                    db.session.add(feedback_answer)
                    db.session.commit()
        else:
            return jsonify({
                    'status': 1,
                    'message': "Error: Authentication failed"
                })
                
        return jsonify({
                    'status': 0,
                    'message': success_msg
                })



    @app.route('/admin/feedbacks/<int:feedbackid>/answers', methods=['GET'])
    @admins_only
    def admin_feedback_answers(feedbackid):
        teams = db.session.query(
                    Teams.id,
                    Teams.name
                )
        teamnames = {}
        for team in teams:
            teamnames[team.id] = team.name

        answers = []
        for answer in ChallengeFeedbackAnswers.query.filter_by(questionid=feedbackid).all():
            answers.append({'id': answer.id, 
                            'team': teamnames[answer.teamid], 
                            'answer': answer.answer, 
                            'timestamp': answer.timestamp})
        data = {}
        data['answers'] = answers
        return jsonify(data)

    @app.route('/admin/feedbacks', defaults={'feedbackid': None}, methods=['POST', 'GET'])
    @app.route('/admin/feedbacks/<int:feedbackid>', methods=['GET', 'DELETE'])
    @admins_only
    @bypass_csrf_protection
    def admin_feedbacks(feedbackid):
        if feedbackid:
            feedback = ChallengeFeedbackQuestions.query.filter_by(id=feedbackid).first_or_404()

            if request.method == 'DELETE':
                ChallengeFeedbackAnswers.query.filter_by(questionid=feedbackid).delete()
                db.session.delete(feedback)
                db.session.commit()
                db.session.close()
                return ('', 204)

            json_data = {
                'id': feedback.id,
                'chalid': feedback.chalid,
                'question': feedback.question,
                'type': feedback.inputtype
            }
            db.session.close()
            return jsonify(json_data)
        else:
            if request.method == 'GET':
                feedbacks = ChallengeFeedbackQuestions.query.all()
                json_data = []
                for feedback in feedbacks:
                    json_data.append({
                        'id': feedback.id,
                        'chalid': feedback.chalid,
                        'question': feedback.question,
                        'type': feedback.inputtype,
                        'extraarg1' : feedback.extraarg1,
                        'extraarg2' : feedback.extraarg2,
                    })
                return jsonify({'results': json_data})
            elif request.method == 'POST':
                question = request.form.get('question')
                chalid = int(request.form.get('chal'))
                inputtype = int(request.form.get('type') or -1)
                extraarg1 = ""
                extraarg2 = ""
                if inputtype == 0:
                    extraarg1 = request.form.get('ratinglowlabel')
                    extraarg2 = request.form.get('ratinghighlabel')
                feedback = ChallengeFeedbackQuestions(chalid=chalid, question=question, inputtype=inputtype, extraarg1=extraarg1, extraarg2=extraarg2)
                db.session.add(feedback)
                db.session.commit()
                json_data = {
                    'id': feedback.id,
                    'chalid': feedback.chalid,
                    'question': feedback.question,
                    'type': feedback.inputtype,
                    'extraarg1' : feedback.extraarg1,
                    'extraarg2' : feedback.extraarg2,
                }
                db.session.close()
                return jsonify(json_data)

    @app.route('/admin/feedbacks/export', methods=['GET'])
    @admins_only
    def admin_export_feedbacks():
        feedbacks = export_feedbacks()
        json_data = json.dumps(feedbacks, indent=4)
        buffer = io.BytesIO()
        buffer.write(json_data.encode('utf-8'))
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="data.json",
            mimetype="application/json"
        )

    @app.route('/admin/feedbacks/export_csv', methods=['GET'])
    @admins_only
    def admin_export_feedbacks_csv():
        feedbacks = export_feedbacks()
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=feedbacks[0].keys())
        writer.writeheader()
        writer.writerows(feedbacks)
        buffer.seek(0)

        return send_file(
            io.BytesIO(buffer.getvalue().encode('utf-8')),
            as_attachment=True,
            download_name="data.csv",
            mimetype="text/csv"
        )

def export_feedbacks():
    export = []
    # Get all challenges
    challenges = Challenges.query.all()
    # sort challenges by category
    challenges = sorted(challenges, key=lambda x: x.category)
    for challenge in challenges:

        # Get questions for this challenge
        questions = ChallengeFeedbackQuestions.query.filter_by(chalid=challenge.id).all()
        for question in questions:

            # For each question, get the answers
            answers = ChallengeFeedbackAnswers.query.filter_by(questionid=question.id).all()
            for answer in answers:

                # get team by teamid
                team = Teams.query.filter_by(id=answer.teamid).first()

                # put everything in a dict
                export.append({
                    'challenge': challenge.name,
                    'category': challenge.category,
                    'team': team.name,
                    'team_email': team.email,
                    'question': question.question,
                    'answer': answer.answer,
                })

    return export