from typing import List

import psycopg2

from config import config

connection = psycopg2.connect(
    database=config.db_name,
    user=config.db_user,
    password=config.db_password,
    host=config.db_host,
    port=config.db_port)


def get_course_list() -> List[str]:
    with connection.cursor() as curr:
        curr.execute('''
            SELECT c_code, c_id FROM "Course" 
        ''')
        return [x for x in curr.fetchall()]


def get_or_create_semester_return_id(semester):
    with connection.cursor() as curr:
        curr.execute('''
                    SELECT s_id FROM "Semester" 
                    where t_id = %s and s_year = %s
                ''', (semester['term'], semester['year']))
        semester_id = curr.fetchone()
        if semester_id is not None:
            return semester_id[0]
        curr.execute('''
                            insert into "Semester" (t_id, s_year) 
                            VALUES ( %s, %s ) 
                            returning s_id;
                        ''', (semester['term'], semester['year']))
        return curr.fetchone()[0]


def semester_offer_data_exists_in_prod(semester_offer, semester_id, course_id):
    result = []
    query = '''
               SELECT so_id FROM "SemesterOffer" 
               WHERE so_section_name = \'%s\' and c_id = %d and so_classroom = \'%s\' and s_id = %d
           ''' % (semester_offer.section, course_id, semester_offer.classroom, semester_id)

    with connection.cursor() as curr:
        curr.execute(query)
        result = curr.fetchone()

    return -1 if result is None else result[0]


def create_semester_offer(semester_offer, semester_id, course_id):
    result = []
    query = '''
                   INSERT INTO "SemesterOffer" (so_capacity, so_section_name, c_id, s_id, so_classroom)
                   VALUES ( %d, \'%s\', %d, %d, \'%s\' )
                   RETURNING so_id
               ''' % (semester_offer.capacity, semester_offer.section, course_id, semester_id, semester_offer.classroom)
    with connection.cursor() as curr:
        curr.execute(query)
        result = curr.fetchone()
    return -1 if result is None else result[0]


def create_semester_offer_timeslots(semester_offer, semester_offer_id):
    insert_values = ''

    for timeslot in semester_offer.slots:
        insert_values += '''( \'%s\'::time, \'%s\'::time, %d, %d ),''' % (
            timeslot.start_time, timeslot.end_time, semester_offer_id, timeslot.day_id)
    insert_values = insert_values[:-1]
    insert_query = " INSERT INTO \"TimeSlot\" (ts_start_time, ts_end_time, so_id, d_id) VALUES %s" % (insert_values,)
    with connection.cursor() as curr:
        curr.execute(insert_query)


def remove_timeslots(so_id):
    with connection.cursor() as curr:
        curr.execute('''
            DELETE FROM "TimeSlot"
            WHERE so_id = %s 
        ''', (so_id,))


def update_semester_offer(semester_offer, so_id, semester_id):
    query = '''
                       UPDATE "SemesterOffer" 
                       set so_capacity = %d, so_section_name = \'%s\',s_id = %d, so_classroom = \'%s\'
                       WHERE so_id = %d
                   ''' % (
        semester_offer.capacity, semester_offer.section, semester_id, semester_offer.classroom, so_id)
    with connection.cursor() as curr:
        curr.execute(query)


def add_professor_teaches(semester_offer_id, professor_ids):
    professor_values = ''
    for professor_id in professor_ids:
        professor_values += '''( %d, %d ),''' % (semester_offer_id, professor_id)
    professor_values = professor_values[:-1]

    query = '''
                       INSERT INTO "ProfessorTeaches" (so_id,p_id) VALUES %s RETURNING so_id
                   ''' % professor_values
    with connection.cursor() as curr:
        curr.execute(query)


def get_professor_id(semester_offer):
    professor_values = ''
    final_result = []
    professors_in_prod = []
    for professor in semester_offer.professor:
        professor_values += f"'{professor}'" + ','
    professor_values = professor_values[:-1]
    query = f'''
               SELECT p_id, p_name FROM "Professor" 
               WHERE p_name in ({professor_values}) '''

    print(query)
    with connection.cursor() as curr:
        curr.execute(query)
        result = [x for x in curr.fetchall()]
    for professor_tuple in result:
        final_result.append(professor_tuple[0])
        professors_in_prod.append(professor_tuple[1])

    missing_professor_names = list(set(semester_offer.professor) - set(professors_in_prod))

    return final_result, missing_professor_names


def create_professor(professors):
    final_result = []
    professor_names = tuple(professors)
    insert_value = ''
    for professor_name in professor_names:
        insert_value += '''( \'%s\', null),''' % (professor_name,)
    insert_value = insert_value[:-1]
    query = ''' INSERT INTO "Professor" (p_name, dept_id)  VALUES  %s  RETURNING p_id''' % insert_value
    with connection.cursor() as curr:
        curr.execute(query)
        result = curr.fetchall()
    for professor_tuple in result:
        final_result.append(professor_tuple[0])

    return final_result


def remove_professor_teaches(semester_offer_id):
    with connection.cursor() as curr:
        curr.execute('''
            DELETE FROM "ProfessorTeaches"
            WHERE so_id=%s
        ''', (semester_offer_id,))
